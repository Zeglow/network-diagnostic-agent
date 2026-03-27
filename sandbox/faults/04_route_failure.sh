#!/bin/bash
TARGET_IP=$(docker exec client getent hosts target | awk '{print $1}')
docker exec client ip route add blackhole $TARGET_IP
echo "Fault injected: route failure"
