#!/bin/bash

echo "Installing packages"
sudo pacman -S --noconfirm - < packages.txt

# Check if yay is installed
if ! command -v yay &> /dev/null; then
    echo "yay is not installed. Installing yay first..."
    # Install yay here if needed
fi

echo "Installing AUR packages"
yay -S --noconfirm - < aur_packages.txt