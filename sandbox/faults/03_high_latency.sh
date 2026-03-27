#!/bin/bash
docker exec client tc qdisc add dev eth0 root netem delay 500ms
echo "Fault injected: high latency 500ms"
