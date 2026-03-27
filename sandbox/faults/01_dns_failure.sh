#!/bin/bash
docker exec client bash -c "cp /etc/resolv.conf /etc/resolv.conf.bak && echo 'nameserver 192.0.2.1' > /etc/resolv.conf"
echo "Fault injected: DNS failure"
