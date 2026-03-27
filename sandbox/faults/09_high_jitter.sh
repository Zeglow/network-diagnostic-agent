#!/bin/bash
docker exec client tc qdisc add dev eth0 root netem delay 100ms 80ms distribution normal
echo "Fault injected: high jitter 100ms +/- 80ms"
