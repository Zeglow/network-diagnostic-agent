#!/bin/bash
docker exec client tc qdisc add dev eth0 root netem loss 10% 25%
echo "Fault injected: intermittent loss"
