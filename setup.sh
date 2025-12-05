#!/bin/bash

scripts/yay_setup.sh
scripts/install_packages.sh
scripts/firewall_setup.sh
scripts/dots_setup.sh
scripts/regreet_setup.sh

# Check for gpu and install appropriate drivers
# (Need to update in the future to install intel / AMD specific drivers
#   although those should just work out of the box)
if lspci | grep -i nvidia > /dev/null 2>&1; then
    echo "NVIDIA GPU detected — running nvidia.sh"
    scripts/nvidia.sh
else
    echo "No NVIDIA GPU detected — skipping NVIDIA setup"
fi
