#!/usr/bin/env bash
# Start the API and the web app together (macOS / Linux).
# Usage:  ./scripts/dev.sh
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "$root/backend/.venv" ]; then
  python3 -m venv "$root/backend/.venv"
  "$root/backend/.venv/bin/pip" install -r "$root/backend/requirements.txt"
fi

"$root/backend/.venv/bin/python" "$root/backend/manage.py" runserver 127.0.0.1:8000 &
api_pid=$!
trap 'kill $api_pid 2>/dev/null || true' EXIT

cd "$root/frontend"
[ -d node_modules ] || npm install
npm run dev
