#!/bin/bash
docker exec target tc qdisc add dev eth0 root tbf rate 100kbit burst 10kb latency 70ms

echo "Fault injected: bandwidth throttle 100kbit"
