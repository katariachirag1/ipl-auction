#!/bin/bash
if [ -n "$GITFARM_ROBOT_USER_KEY" ]; then
  exec /usr/bin/ssh -l nobody \
    -o SendEnv=GITFARM_ROBOT_USER_KEY \
    -o PreferredAuthentications=keyboard-interactive \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "$@"
else
  exec /usr/bin/ssh "$@"
fi
