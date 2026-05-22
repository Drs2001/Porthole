#!/bin/bash
# Wait for Hyprland socket to be available
until [ -S "/run/user/0/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket.sock" ] 2>/dev/null ||
      ls /run/user/0/hypr/ 2>/dev/null | grep -q .; do
    sleep 0.5
done
exec python /root/installer/installer.py