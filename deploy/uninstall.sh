#!/usr/bin/env bash
# Stop my_secretary and remove the service. Your data in ~/.secretary stays.
# If v1's unit was kept (my-secretary.service.v1.bak), this offers to put it back.
set -euo pipefail
UNIT="$HOME/.config/systemd/user/my-secretary.service"

systemctl --user disable --now my-secretary.service 2>/dev/null || true
rm -f "$UNIT"
if [ -f "$UNIT.v1.bak" ]; then
  read -r -p "ใส่ service ของ v1 กลับไหม? (ต้องอยู่ใน branch main ด้วย: git switch main) [y/N] " yes
  if [ "${yes:-n}" = "y" ]; then mv "$UNIT.v1.bak" "$UNIT"; fi
fi
systemctl --user daemon-reload
echo "เอา service ออกแล้ว · ข้อมูลใน ~/.secretary ยังอยู่"
