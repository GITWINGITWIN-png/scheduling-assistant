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

command -v uv >/dev/null || { echo "ไม่พบ uv (ต้องมี ~/.local/bin/uv)"; exit 1; }
command -v npm >/dev/null || { echo "ไม่พบ npm (ต้องใช้ build หน้าเว็บ)"; exit 1; }

echo "1/4 ติดตั้งแพ็กเกจ Python ตาม uv.lock"
(cd "$REPO/backend" && uv sync --frozen)

echo "2/4 build หน้าเว็บ"
(cd "$REPO/frontend" && npm ci --no-fund --no-audit && npm run build)

echo "3/4 เขียนไฟล์ service"
mkdir -p "$UNIT_DIR"
if [ -f "$UNIT" ] && ! grep -q "my_secretary v2" "$UNIT"; then
  cp "$UNIT" "$UNIT.v1.bak"   # v1's unit file, kept so v1 can be brought back
  echo "    เก็บไฟล์ service เดิมของ v1 ไว้ที่ $UNIT.v1.bak"
fi
sed -e "s|@REPO@|$REPO|g" -e "s|@HOST@|$HOST|g" "$REPO/deploy/my-secretary.service" > "$UNIT"
systemctl --user daemon-reload

echo "4/4 เปิดและรีสตาร์ท"
systemctl --user enable my-secretary.service >/dev/null
systemctl --user restart my-secretary.service

for _ in $(seq 1 30); do
  if curl -fs "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    echo
    echo "เลขาทำงานแล้ว: http://localhost:8000  (host $HOST)"
    echo "ดูสถานะ:   systemctl --user status my-secretary"
    echo "ดู log:    journalctl --user -u my-secretary -f"
    exit 0
  fi
  sleep 1
done
echo "เลขายังไม่ตอบใน 30 วินาที · ดูสาเหตุ: journalctl --user -u my-secretary -n 50"
exit 1
