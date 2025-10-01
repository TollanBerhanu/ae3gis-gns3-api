#!/usr/bin/env bash


# if [ "$#" -lt 1 ]; then
#   echo "Usage: $0 <server_ip> [interval_seconds]"
#   exit 1
# fi
dhclient -v -1

ifconfig