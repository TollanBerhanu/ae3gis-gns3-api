#!/bin/bash
set -euo pipefail

# --- CONFIG: change these ---
USER="ftpuser"
PASS="ftppass"
IFACE="eth0"
PORT=21
MIN=10
MAX=30
REMOTE_CD="/home/ftpuser/ftp"   # e.g. "/home/ftpuser" or leave empty to skip

rand_int() {
  local range=$((MAX - MIN + 1))
  echo $(( MIN + RANDOM % range ))
}

while true; do
  sleep "$(rand_int)"

  TARGET="192.168.0.103"
  echo "Attempting FTP upload to $TARGET ..."

  # unique name each time (UTC timestamp + random)
  TS=$(date -u +%Y%m%dT%H%M%SZ)
  BASENAME="ftp_test_${TS}_${RANDOM}.txt"
  LOCAL_FILE="/tmp/${BASENAME}"
  REMOTE_FILENAME="${BASENAME}"

  # create a small file to upload
  cat > "$LOCAL_FILE" <<EOF
Hello from $(hostname) at $(date --iso-8601=seconds)
This is a harmless test file for FTP upload.
Local path: $LOCAL_FILE
Remote name: $REMOTE_FILENAME
EOF

  # classic ftp client (non-interactive)
  if ftp -pinv "$TARGET" <<EOF
user $USER $PASS
binary
passive
cd $REMOTE_CD
put $LOCAL_FILE $REMOTE_FILENAME
bye
EOF
  then
    echo "Upload to $TARGET succeeded: $REMOTE_FILENAME"
    rm -f -- "$LOCAL_FILE"  # optional: clean up local file
  else
    echo "Upload to $TARGET failed: $REMOTE_FILENAME"
    # keep local file for troubleshooting
  fi
done
