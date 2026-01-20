import socket
import struct
import argparse
import os
import zlib

def xor_decrypt(data, key):
    key_bytes = key.encode('utf-8')
    decrypted = bytearray()
    for i in range(len(data)):
        decrypted.append(data[i] ^ key_bytes[i % len(key_bytes)])
    return bytes(decrypted)

def parse_packet(packet):
    ip_header = packet[0:20]
    iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
    
    version_ihl = iph[0]
    ihl = version_ihl & 0xF
    iph_length = ihl * 4
    
    tcp_idx = iph_length
    tcp_header = packet[tcp_idx:tcp_idx+20]
    tcph = struct.unpack('!HHLLBBHHH', tcp_header)
    
    src_port = tcph[0]
    dst_port = tcph[1]
    seq_num = tcph[2]
    ack_num = tcph[3]
    
    doff_reserved = tcph[4]
    tcph_length = (doff_reserved >> 4) * 4
    
    flags = tcph[5]
    win_size = tcph[6]
    # URG Ptr at index 8 is theoretically unused now
    
    options_data = packet[tcp_idx+20 : tcp_idx+tcph_length]
    
    ts_val = 0
    ts_ecr = 0
    
    i = 0
    while i < len(options_data):
        kind = options_data[i]
        if kind == 0: break
        if kind == 1:
            i += 1
            continue
        if i+1 >= len(options_data): break
        length = options_data[i+1]
        if kind == 8 and length == 10:
            if i+10 <= len(options_data):
                ts_val = int.from_bytes(options_data[i+2:i+6], 'big')
                ts_ecr = int.from_bytes(options_data[i+6:i+10], 'big')
            break
        i += length
    
    ip_id = iph[3]

    return {
        'src_ip': socket.inet_ntoa(iph[8]),
        'dst_port': dst_port,
        'src_port': src_port,
        'flags': flags,
        'data_fields': {
            'id': ip_id,
            'seq': seq_num,
            'ack': ack_num,
            'win': win_size,
            'ts_val': ts_val,
            'ts_ecr': ts_ecr
        }
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080, help='Listening Port (Filter)')
    parser.add_argument('--key', required=True, help='Decryption Key')
    args = parser.parse_args()
    
    buffers = {}
    completed_sids = set()
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
    except PermissionError:
        print("Error: Requires root privileges (sudo).")
        return

    print(f"Listening for Stealth Traffic (20 bytes/pkt, No URG) on port {args.port}...")
    
    while True:
        try:
            packet, addr = s.recvfrom(65565)
            p = parse_packet(packet)
            
            if p['dst_port'] != args.port:
                continue
            
            # Mimic Mode logic (SYN or PSH/ACK)
            if not ((p['flags'] & 0x02) or (p['flags'] & 0x10)):
                continue
            
            d = p['data_fields']
            
            # Reconstruct 20 bytes (No URG)
            chunk = (
                d['id'].to_bytes(2, 'big') + 
                d['seq'].to_bytes(4, 'big') + 
                d['ack'].to_bytes(4, 'big') + 
                d['win'].to_bytes(2, 'big') + 
                d['ts_val'].to_bytes(4, 'big') + 
                d['ts_ecr'].to_bytes(4, 'big')
            )
            
            sid = p['src_port']
            if sid in completed_sids: continue

            if sid not in buffers:
                buffers[sid] = bytearray()
                print(f"[*] New stream detected from Port {sid}")
            
            buffers[sid].extend(chunk)
            
            buf = buffers[sid]
            if len(buf) > 80 and len(buf) % 100 == 0: 
                 try:
                     dec = xor_decrypt(buf, args.key)
                     comp_size = struct.unpack('!Q', dec[0:8])[0]
                     
                     if len(dec) >= 8 + comp_size:
                         comp_data = dec[8 : 8+comp_size]
                         try:
                             decompressed = zlib.decompress(comp_data)
                         except zlib.error:
                             continue
                         
                         # Parse: [Name][0x00][Body][CRC32(4)]
                         if len(decompressed) < 5: continue
                         
                         null_pos = decompressed.find(b'\x00')
                         if null_pos != -1:
                             filename = decompressed[:null_pos].decode('utf-8', errors='ignore')
                             
                             # Extract Integrity
                             file_content_with_crc = decompressed[null_pos+1:]
                             if len(file_content_with_crc) < 4: continue
                             
                             file_content = file_content_with_crc[:-4]
                             received_crc = struct.unpack('!I', file_content_with_crc[-4:])[0]
                             
                             # Validata Integrity
                             calc_crc = zlib.crc32(file_content)
                             
                             if calc_crc == received_crc:
                                 if not filename: filename = f"output_{sid}.bin"
                                 safe_name = os.path.basename(filename)
                                 
                                 with open(f"received_{safe_name}", 'wb') as f:
                                     f.write(file_content)
                                     
                                 print(f"[SUCCESS] Saved {safe_name} ( Integrity Verified )")
                                 del buffers[sid]
                                 completed_sids.add(sid)
                             else:
                                 print(f"[!] Warning: CRC32 Mismatch for {filename}. Corrupt file.")
                 except:
                     pass
                     
        except KeyboardInterrupt:
            break
        except Exception:
            pass

if __name__ == "__main__":
    main()
