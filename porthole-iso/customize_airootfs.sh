#!/usr/bin/env bash
set -ex

# Enable services
systemctl enable NetworkManager.service
systemctl enable power-profiles-daemon.service

# Allow liveuser passwordless sudo (needed for installer)
echo "liveuser ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/liveuser

# Ensure skel perms
chmod -R 755 /etc/skel/.config