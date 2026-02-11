#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-8000}"
URL="http://127.0.0.1:${PORT}/"

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Using existing server on port $PORT"
  if command -v open >/dev/null 2>&1; then
    open "$URL"
  else
    echo "Open this URL in your browser: $URL"
  fi
  exit 0
fi

echo "Starting app server on port $PORT"
echo "Press Ctrl+C to stop"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

python3 server.py >/dev/null 2>&1 &
SERVER_PID=$!

sleep 1

if command -v open >/dev/null 2>&1; then
  open "$URL"
else
  echo "Open this URL in your browser: $URL"
fi

wait "$SERVER_PID"
