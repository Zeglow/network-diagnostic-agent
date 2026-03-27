#!/bin/bash
docker exec client tc qdisc add dev eth0 root netem duplicate 20%
echo "Fault injected: duplicate packets 20%"
