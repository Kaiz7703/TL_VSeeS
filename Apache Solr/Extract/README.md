# TCP Steganography Tool (Linux Only)

This tool allows you to securely transfer files by hiding data within the TCP/IP headers of empty SYN packets. It offers a covert channel that bypasses some forms of traffic analysis.

## Features
- **Integrity Verified**: Uses CRC32 checksums to ensure file correctness.
- **Stealthy**: Dropped suspicious `URG` flags. Looks like normal Traffic (SYN -> PSH+ACK).
- **High Capacity**: **20 bytes** per packet (via IP ID, SEQ, ACK, WIN, TS).
- **Compression**: `zlib` compression enabled.

## Prerequisites
- **OS**: Linux (Ubuntu, Debian, Kali, etc.)
- **Python**: Python 3.x
- **Privileges**: Root / `sudo`

## Capacity Note
The protocol packs **20 bytes** into:
- 2 Bytes: IP ID
- 4 Bytes: TCP Sequence Number
- 4 Bytes: TCP Acknowledgment Number
- 2 Bytes: TCP Window Size
- **8 Bytes: TCP Timestamp Option**

## Technical Deep Dive: Multi-file Multiplexing
**How do we send multiple files without mixing them up?**

The tool uses **Source Port Multiplexing**. 
1.  **Sender**: When you send a file (e.g., `image.jpg`), the script assigns a random, unique **TCP Source Port** (e.g., 12345) to that specific file stream. All 14-byte chunks of `image.jpg` are sent in packets with `Source Port = 12345`.
2.  **Sender**: If you send a second file (`data.db`) simultaneously, it gets a *different* Source Port (e.g., 54321).
3.  **Receiver**: The receiver looks at the Source Port of every incoming packet.
    *   Packet from Port 12345? -> Append data to `Buffer_Image`.
    *   Packet from Port 54321? -> Append data to `Buffer_Data`.

This acts effectively as a **Session ID**, allowing the receiver to reconstruct multiple independent files being received at the exact same time.

## Usage

### 1. Start the Receiver
On the machine that will **receive** files:

```bash
# Syntax: sudo python3 receiver.py --port <LISTENING_PORT> --key <PASSWORD>
sudo python3 receiver.py --port 8080 --key "mysecretkey"
```

The receiver will now listen on port 8080. It will ignore normal traffic and only process packets that match our steganography protocol.

### 2. Send Files
On the machine that is **sending** files:

```bash
# Syntax: sudo python3 sender.py --target <RECEIVER_IP> --port <RECEIVER_PORT> --key <PASSWORD> [FILES...]

# Example: Send a single secret file
sudo python3 sender.py --target 192.168.1.50 --port 8080 --key "mysecretkey" top_secret.txt

# Example: Send multiple files at once
sudo python3 sender.py --target 192.168.1.50 --port 8080 --key "mysecretkey" image.jpg database.db logs.txt
```

## Troubleshooting

### "Permission Error"
You must run both scripts with `sudo`.

### "No files received" or Packets Dropped
1.  **Firewall**: Ensure the receiver's firewall allows incoming TCP traffic on the port.
    ```bash
    sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
    ```
2.  **RST Packets**: The Linux kernel may automatically send "Connection Reset" (RST) packets because it doesn't recognize the connection. This might disrupt the stream or alert IDSs. To prevent this, block outgoing RSTs:
    ```bash
    sudo iptables -A OUTPUT -p tcp --tcp-flags RST RST -j DROP
    ```

### "Address already in use"
The receiver uses a Raw Socket, so it shouldn't conflict with normal listeners, but if you have a web server running on port 8080, it's better to pick a different port (e.g., 9999) to avoid noise.
