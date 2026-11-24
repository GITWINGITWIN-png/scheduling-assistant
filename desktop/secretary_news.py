#!/usr/bin/python3
"""Send news to the secretary (B10): one line from any project puts a news file in the secretary's inbox.

    secretary-news report "เสร็จ: ตัวแยกคำภาษาไทย" --body "ขั้นต่อไป: เทสต์กับข้อมูลจริง"
    secretary-news report "รอคุณเลือกว่าจะใช้ model ไหน" --needs-you
    secretary-news schedule "ส่งรายงาน datacom" --due 2026-11-13T17:00 --minutes 120
    secretary-news status "backtest รอบที่ 14" --state failed --body "หน่วยความจำไม่พอที่ขั้น 3"

    /usr/bin/python3 desktop/secretary_news.py install     # the `secretary-news` command (~/.local/bin)
    /usr/bin/python3 desktop/secretary_news.py uninstall   # take it away again

It is docs/CONNECT.md as a command: the project is the folder under ~/Projects you run it from
(or --project), and the file is written whole and then renamed into place, so the secretary never
reads half a file. The secretary reads its inbox every 5 minutes while the round "อ่านข่าวจากโปรเจค"
(read news from projects) is on. The projects are told to use it by the note "เชื่อมกับเลขา" (connect with the secretary) writes into each one
(backend/app/features/projects/connect.py).

Standard library only, so it runs from any project and any Python, without the secretary's venv.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parent.parent
COMMAND = Path.home() / ".local" / "bin" / "secretary-news"
STATES = ("running", "done", "failed", "paused")


class Refused(ValueError):
    """What was asked can't be sent as it is. The message says why, in the user's words."""


def setting(name: str, default: Path) -> Path:
    """SECRETARY_<name> as the secretary reads it: the environment first, then backend/.env."""
    key = f"SECRETARY_{name}"
    value = os.environ.get(key)
    if value is None:
        try:
            for line in (REPO / "backend" / ".env").read_text().splitlines():
                k, sep, v = line.partition("=")
                if sep and k.strip() == key:
                    value = v.strip().strip("\"'")
        except OSError:
            pass
    return Path(value).expanduser() if value else default


def data_dir() -> Path:
    return setting("DATA_DIR", Path.home() / ".secretary")


def projects_dir() -> Path:
    return setting("PROJECTS_DIR", Path.home() / "Projects")


def project_of(cwd: Path, root: Path) -> str | None:
    """The folder directly under ~/Projects that `cwd` is in (its name is the project's in the registry)."""
    try:
        rel = cwd.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def _iso(value: str, what: str) -> str:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise Refused(f"{what} ต้องเป็นวันเวลาแบบ 2026-11-13T17:00 (ได้ “{value}”)") from None
    return value


def item(kind: str, title: str, *, body: str = "", link: str = "", needs_you: bool = False, failed: bool = False,
         due: str = "", minutes: int | None = None, state: str = "", at: str = "") -> dict:
    """One news file's content (docs/CONNECT.md's fields), checked."""
    title = re.sub(r"\s+", " ", title).strip()  # one line, as the secretary shows it
    if not title:
        raise Refused("ต้องมีหัวข้อ")
    news: dict = {"kind": kind, "title": title[:300]}
    if body.strip():
        news["body"] = body.strip()[:2000]
    if link.strip():
        news["link"] = link.strip()
    if needs_you:
        news["needs_you"] = True
    if failed:
        news["failed"] = True
    if at:
        news["at"] = _iso(at, "--at")
    if kind == "schedule":
        if not due:
            raise Refused("schedule ต้องมี --due (กำหนดส่ง)")
        news["due"] = _iso(due, "--due")
        if minutes is not None:
            if minutes <= 0:
                raise Refused("--minutes ต้องมากกว่า 0")
            news["minutes"] = minutes
    if kind == "status":
        if state not in STATES:
            raise Refused(f"status ต้องมี --state เป็น {' · '.join(STATES)}")
        news["status"] = state
    return news


def send(news: dict, project: str, inbox: Path, at: datetime | None = None) -> Path:
    """Write the file whole under a hidden name (the secretary skips names starting with "."),
    then rename it into place in one step. -> where it went."""
    folder = inbox / project
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{(at or datetime.now()):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}.json"
    hidden = folder / f".{name}.tmp"
    hidden.write_text(json.dumps(news, ensure_ascii=False, indent=1) + "\n")
    os.replace(hidden, folder / name)
    return folder / name


def round_on(data: Path) -> bool | None:
    """Whether the secretary reads its inbox now (the round "read news from projects"), or None if unknown."""
    try:
        db = sqlite3.connect(f"file:{data / 'secretary.db'}?mode=ro", uri=True)
        try:
            row = db.execute("select value from settings where key = 'clock.enabled'").fetchone()
        finally:
            db.close()
        return bool(json.loads(row[0]).get("inbox", False)) if row else False
    except (sqlite3.Error, ValueError, TypeError):
        return None


def install() -> str:
    if COMMAND.is_symlink() and COMMAND.resolve() == HERE:
        return f"ติดตั้งอยู่แล้ว: {COMMAND} → {HERE}"
    if COMMAND.exists() or COMMAND.is_symlink():
        raise Refused(f"มี {COMMAND} อยู่แล้ว และไม่ใช่ของเลขา: ไม่ทับให้")
    COMMAND.parent.mkdir(parents=True, exist_ok=True)
    COMMAND.symlink_to(HERE)
    on_path = str(COMMAND.parent) in os.environ.get("PATH", "").split(os.pathsep)
    return f"ติดตั้งแล้ว: {COMMAND} → {HERE}" + ("" if on_path else f" · {COMMAND.parent} ยังไม่อยู่ใน PATH")


def uninstall() -> str:
    if COMMAND.is_symlink() and COMMAND.resolve() == HERE:
        COMMAND.unlink()
        return f"เอาออกแล้ว: {COMMAND}"
    return "ไม่ได้ติดตั้งไว้ (หรือเป็นไฟล์อื่นที่ไม่ใช่ของเลขา: ไม่แตะ)"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="secretary-news", description="ส่งข่าวจากโปรเจคให้เลขา (my_secretary)")
    sub = p.add_subparsers(dest="kind", required=True)
    for kind, about in (("report", "มีอะไรใหม่: จบขั้นหรือ milestone ผลรัน สรุปผล"),
                        ("schedule", "กำหนดส่ง: กลายเป็นงานในตารางของเลขา"),
                        ("status", "งานที่รันเองจบหรือล้ม")):
        k = sub.add_parser(kind, help=about)
        k.add_argument("title", help="หัวข้อบรรทัดเดียว")
        k.add_argument("--body", default="", help="รายละเอียด")
        k.add_argument("--link", default="", help="ลิงก์ไปดูเพิ่ม")
        k.add_argument("--needs-you", action="store_true", help="ต้องให้ผู้ใช้ตัดสินหรือตรวจ")
        k.add_argument("--failed", action="store_true", help="งานล้ม")
        k.add_argument("--at", default="", help="เวลาที่เกิด (ไม่ใส่ = ตอนที่เลขาอ่าน)")
        k.add_argument("--project", default="", help="ชื่อโฟลเดอร์โปรเจคใน ~/Projects (ไม่ใส่ = โฟลเดอร์ที่อยู่ตอนนี้)")
        if kind == "schedule":
            k.add_argument("--due", required=True, help="กำหนดส่ง เช่น 2026-11-13T17:00")
            k.add_argument("--minutes", type=int, help="เวลาที่ต้องใช้ (นาที)")
        if kind == "status":
            k.add_argument("--state", required=True, choices=STATES)
    sub.add_parser("install", help=f"ติดตั้งคำสั่ง secretary-news ที่ {COMMAND}")
    sub.add_parser("uninstall", help="เอาคำสั่งออก")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.kind in ("install", "uninstall"):
            print(install() if args.kind == "install" else uninstall())
            return 0
        project = args.project.strip() or project_of(Path.cwd(), projects_dir())
        if not project or "/" in project or project.startswith("."):
            raise Refused(f"อยู่นอก {projects_dir()}: ใส่ --project <ชื่อโฟลเดอร์ของโปรเจค>")
        news = item(args.kind, args.title, body=args.body, link=args.link, needs_you=args.needs_you, failed=args.failed,
                    due=getattr(args, "due", "") or "", minutes=getattr(args, "minutes", None),
                    state=getattr(args, "state", "") or "", at=args.at)
        send(news, project, data_dir() / "inbox")
    except Refused as exc:
        print(f"secretary-news: {exc}", file=sys.stderr)
        return 2
    print(f"ส่งข่าวให้เลขาแล้ว · {project} · {args.kind}: {news['title']}")
    if round_on(data_dir()) is False:
        print("(เลขาจะอ่านเมื่อเปิดรอบ “อ่านข่าวจากโปรเจค” ที่หน้าตั้งค่า)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
