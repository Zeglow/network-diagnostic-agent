#!/bin/bash
# 恢复 client DNS
docker exec client bash -c "if [ -f /etc/resolv.conf.bak ]; then cp /etc/resolv.conf.bak /etc/resolv.conf && rm /etc/resolv.conf.bak; fi"

# 清除 client iptables
docker exec client iptables -F
docker exec client iptables -P INPUT ACCEPT
docker exec client iptables -P OUTPUT ACCEPT
docker exec client iptables -P FORWARD ACCEPT

# 清除 client tc 和 blackhole 路由
docker exec client tc qdisc del dev eth0 root 2>/dev/null || true
docker exec client ip route flush type blackhole 2>/dev/null || true

# 清除 target tc
docker exec target tc qdisc del dev eth0 root 2>/dev/null || true

echo "All faults cleared"
