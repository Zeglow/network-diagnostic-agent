#!/bin/bash
docker exec client tc qdisc add dev eth0 root netem loss 30%
echo "Fault injected: packet loss 30%"
