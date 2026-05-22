# Only launch on tty1, not on every terminal
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec hyprland --i-am-really-stupid
fi