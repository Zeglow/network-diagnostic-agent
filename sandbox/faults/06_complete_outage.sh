#!/bin/bash
docker exec client iptables -A OUTPUT -j DROP
echo "Fault injected: complete outage"
