#!/bin/bash

sudo cp -rf ../dots/greetd/* /etc/greetd/

sudo systemctl enable greetd.service
