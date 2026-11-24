#!/usr/bin/env bash
# Install or update my_secretary v2 as an always-on systemd *user* service.
# Run again after every `git pull`. It rebuilds what changed and restarts the service.
#
#   ./deploy/install.sh               # this computer only (127.0.0.1:8000)
#   HOST=0.0.0.0 ./deploy/install.sh  # every network interface (not recommended before B8)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="$UNIT_DIR/my-secretary.service"

command -v uv >/dev/null || { echo "uv not found (expected ~/.local/bin/uv)"; exit 1; }
command -v npm >/dev/null || { echo "npm not found (needed to build the web page)"; exit 1; }

echo "1/4 installing the Python packages from uv.lock"
(cd "$REPO/backend" && uv sync --frozen)

echo "2/4 building the web page"
(cd "$REPO/frontend" && npm ci --no-fund --no-audit && npm run build)

echo "3/4 writing the service file"
mkdir -p "$UNIT_DIR"
if [ -f "$UNIT" ] && ! grep -q "my_secretary v2" "$UNIT"; then
  cp "$UNIT" "$UNIT.v1.bak"   # v1's unit file, kept so v1 can be brought back
  echo "    the old v1 service file is kept at $UNIT.v1.bak"
fi
sed -e "s|@REPO@|$REPO|g" -e "s|@HOST@|$HOST|g" "$REPO/deploy/my-secretary.service" > "$UNIT"
systemctl --user daemon-reload

echo "4/4 enabling and restarting"
systemctl --user enable my-secretary.service >/dev/null
systemctl --user restart my-secretary.service

for _ in $(seq 1 30); do
  if curl -fs "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    echo
    echo "The secretary is running: http://localhost:8000  (host $HOST)"
    echo "Status:   systemctl --user status my-secretary"
    echo "Log:      journalctl --user -u my-secretary -f"
    exit 0
  fi
  sleep 1
done
echo "No answer from the secretary within 30 seconds. To see why: journalctl --user -u my-secretary -n 50"
exit 1
