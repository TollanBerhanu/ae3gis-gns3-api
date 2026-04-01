#!/usr/bin/env bash

dhclient -v -1

MIN=5
MAX=30
CURL_TIMEOUT=10

# helper to pick a random integer in [MIN,MAX]
rand_int() {
  local range=$((MAX - MIN + 1))
  echo $(( MIN + RANDOM % range ))
}

# main loop: pick a random host each iteration, sleep random time, curl it
while true; do
  sleep_for=$(rand_int)
  sleep "$sleep_for"

  # choose a random host from the HOSTS array
  TARGET="192.168.0.102"

  # perform curl (discard body), capture exit status
  if curl -sS --max-time "$CURL_TIMEOUT" "http://$TARGET:$PORT/" >/dev/null; then
    status="ok"
  else
    status="fail"
  fi

  printf '%s curl -> %s:%s (%s) slept %ss\n' "$(date --iso-8601=seconds)" "$TARGET" "$PORT" "$status" "$sleep_for"
done


