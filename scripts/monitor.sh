#!/bin/bash

# 1) tails container logs for ERROR
# 2) hits /metrics and prints the top-5 counters every 10s

# Tail container logs for ERROR in background
docker-compose -f docker/compose.yml logs -f | grep error &

# Hit /metrics and print top-5 counters every 10s
while true; do
    curl -s http://localhost/metrics | grep -v "^#" | sort -nr | head -10
    sleep 2
done