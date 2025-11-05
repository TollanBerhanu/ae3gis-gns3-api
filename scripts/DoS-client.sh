#!/usr/bin/env bash
SERVER_IP="192.168.0.100"
# requests per batch
CONCURRENCY="${CONCURRENCY:-20}"

dhclient -v -1

echo "[http] Server=$SERVER_IP Interval=${INTERVAL}s Concurrency=$CONCURRENCY"

while true; do
  for i in $(seq 1 "$CONCURRENCY"); do
    # run curl in background, discard body, print HTTP code + time_total
    curl -sS -o /dev/null -w "%{http_code} %{time_total}\n" "http://$SERVER_IP/" &
  done
done
