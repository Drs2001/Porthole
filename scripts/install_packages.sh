#!/bin/bash

# Check if yay is installed
if ! command -v yay &> /dev/null; then
    echo "yay is not installed. Installing yay first..."
    # Install yay here if needed
fi

echo "Installing packages from packages.txt..."
yay -S --noconfirm - < packages.txt