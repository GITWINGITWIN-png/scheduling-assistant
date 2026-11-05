"""ดึงตัวเลขของ repo ต้นแบบจาก GitHub API แล้วเก็บเป็น repos.json (snapshot)

ทำไมแยกเป็นไฟล์: แผนที่ต้อง build ได้แม้ไม่มีเน็ต และตัวเลข (ดาว · วันที่ push) ต้องมาจากที่เดียวที่ตรวจสอบได้
ไม่ใช่พิมพ์มือลงใน spec · อยากได้ตัวเลขใหม่ก็รันไฟล์นี้อีกครั้ง แล้ว build ใหม่

ใช้:  python3 docs/reference-map/fetch_repos.py      (ต้องมี gh CLI ที่ล็อกอินแล้ว)
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import REPOS  # noqa: E402 — รายชื่อ repo อยู่ที่เดียว (repos.py)

FIELDS = ("[.full_name, .stargazers_count, .pushed_at, .language, .archived, "
          "(.license.spdx_id // \"-\"), (.description // \"\")]")


def fetch(full_name: str) -> dict:
    out = subprocess.run(["gh", "api", f"repos/{full_name}", "--jq", FIELDS],
                         check=True, capture_output=True, text=True).stdout
    name, stars, pushed, lang, archived, spdx, desc = json.loads(out)
    return dict(full_name=name, stars=stars, pushed=pushed[:10], language=lang,
                archived=archived, spdx=spdx, description=desc)


def main() -> None:
    data = dict(fetched_at=date.today().isoformat(), repos={})
    for key, full_name in REPOS.items():
        data["repos"][key] = fetch(full_name)
        print(f"{key:5} {full_name:42} ★{data['repos'][key]['stars']}")
    out = Path(__file__).with_name("repos.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"เขียน {out}")


if __name__ == "__main__":
    main()
