#!/bin/bash
echo "Monitoring logs and metrics..."
tail -f /var/log/app.log | grep ERROR &
while true; do
    curl -s http://localhost:8000/metrics | grep -v "^#" | sort -nr | head -5
    sleep 10
done