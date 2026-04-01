#!/usr/bin/env bash

dhclient -v -1

curl -k -s -m .1 -d "username=admin&password=secureP@ssw0rd!" https://192.168.0.55:4433/submit