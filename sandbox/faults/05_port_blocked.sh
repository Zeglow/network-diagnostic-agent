#!/bin/bash
docker exec client iptables -A OUTPUT -p tcp --dport 80 -j REJECT
echo "Fault injected: port 80 blocked"
