#!/bin/bash
echo Waiting 10 seconds ...
sleep 60
cd /home/pi/code/einkdisplay
flask run > log.log &


