#!/bin/bash

# Download Porthole Desktop Environment dots
git clone https://github.com/Drs2001/PortholeDE.git ~/.config/quickshell/porthole

# Copy rofi dots
cp -r dots/rofi ~/.config/

# Copy Hyprland dots
cp -r dots/hypr ~/.config/

# Copy qt6 dots
cp -r dots/qt6ct ~/.config/

# Download and install Tela icon theme
git clone https://github.com/vinceliuice/Tela-icon-theme.git
Tela-icon-theme/install.sh

# Download and install We10XOS cursors
git clone https://github.com/yeyushengfan258/We10XOS-cursors.git
We10XOS-cursors/install.sh
