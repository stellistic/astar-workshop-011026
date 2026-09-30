#!/usr/bin/env bash
# Sends one JSON command to the capture driver. Usage: cap '{"op":"info"}'
set -euo pipefail
PORT="${CAPTURE_PORT:-9555}"
curl -sS -X POST "http://127.0.0.1:${PORT}/cmd" -H 'content-type: application/json' --data-binary "$1"
echo
