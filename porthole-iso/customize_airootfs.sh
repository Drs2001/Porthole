#!/usr/bin/env bash
set -ex

# Enable services
systemctl enable NetworkManager.service
systemctl enable power-profiles-daemon.service

# Set up root's XDG runtime dir for the live session
mkdir -p /run/user/0
chmod 700 /run/user/0

# Ensure skel perms
chmod -R 755 /etc/skel/.config