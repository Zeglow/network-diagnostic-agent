#!/bin/bash
# Restore client DNS
docker exec client bash -c "if [ -f /etc/resolv.conf.bak ]; then cp /etc/resolv.conf.bak /etc/resolv.conf && rm /etc/resolv.conf.bak; fi"

# Clear client iptables
docker exec client iptables -F
docker exec client iptables -P INPUT ACCEPT
docker exec client iptables -P OUTPUT ACCEPT
docker exec client iptables -P FORWARD ACCEPT

# Clear client tc and blackhole routes
docker exec client tc qdisc del dev eth0 root 2>/dev/null || true
docker exec client ip route flush type blackhole 2>/dev/null || true

# Clear target tc
docker exec target tc qdisc del dev eth0 root 2>/dev/null || true

echo "All faults cleared"