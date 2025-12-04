#!/bin/bash

sudo pacman -S ufw --noconfirm
sudo systemctl enable ufw
sudo systemctl start ufw
sudo ufw enable