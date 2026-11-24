"""Course materials → the course folder (U1, B3 step 7). Runs inside the Classroom round.

For each followed course, the files attached to its material posts ("เนื้อหา" (content)), its
assignments and its announcements are downloaded into the course folder chosen when
you followed it (e.g. ~/Projects/datacom/สื่อ). Google Docs/Slides/Sheets become PDFs.
Links, YouTube videos and forms are kept as links on the item (the schedule page and,
from B4, the morning summary list them).

A file is downloaded once: its Drive id is remembered on the item, so a re-run, a rename
in Classroom or an undo never fetches it again. Each round's downloads are one line in
สิ่งที่เลขาทำ (what the secretary did), and its ย้อนกลับ (undo) deletes those files (the record that they were fetched
stays, so they don't come back).
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.connectors import classroom as cr
from app.core import actions
from app.core.db import now, session
from app.features.classroom import sync
from app.features.classroom.tables import Course, CourseItem

log = logging.getLogger(__name__)


def _parts(materials: list[dict]) -> tuple[list[tuple[str, str]], list[dict]]:
    """Classroom's materials list -> ([(drive id, title)], [{"title", "url"}])."""
    files, links = [], []
    for m in materials:
        if f := m.get("driveFile", {}).get("driveFile"):
            files.append((f["id"], f.get("title", "")))
        elif v := m.get("youtubeVideo"):
            links.append({"title": v.get("title", "YouTube"), "url": v.get("alternateLink", "")})
        elif link := m.get("link"):
            links.append({"title": link.get("title") or link.get("url", ""), "url": link.get("url", "")})
        elif form := m.get("form"):
            links.append({"title": form.get("title", "ฟอร์ม"), "url": form.get("formUrl", "")})
    return files, links


def _sources(course_id: str) -> list[tuple[str, str, str, str, list[dict]]]:
    """Everything in the course that can carry materials -> [(id, kind, title, link, materials)]."""
    out = [(m["id"], "material", m.get("title", ""), m.get("alternateLink", ""), m.get("materials", []))
           for m in cr.materials(course_id)]
    out += [(w["id"], "work", w.get("title", ""), w.get("alternateLink", ""), w.get("materials", []))
            for w in cr.coursework(course_id)]
    out += [(a["id"], "announcement", (a.get("text", "") or "ประกาศ").splitlines()[0][:120], a.get("alternateLink", ""),
             a.get("materials", [])) for a in cr.announcements(course_id)]
    return [x for x in out if x[4]]


def fetch(course_id: str) -> str | None:
    """sync.AFTER_FOLLOWED hook: download what's new for one followed course. -> a line, or None."""
    with session() as s:
        course = s.get(Course, course_id)
        folder, name = Path(course.folder), course.name
    saved: list[str] = []
    skipped = 0
    for item_id, kind, title, link, materials in _sources(course_id):
        files, links = _parts(materials)
        with session() as s:
            item = s.get(CourseItem, item_id)
            if item is None:
                item = CourseItem(id=item_id, course_id=course_id, kind=kind, title=title, link=link)
                s.add(item)
            have = {f.get("drive_id") for f in item.files or []}
            known = list(item.files or [])
            item.links = links
            item.synced_at = now()
        for drive_id, file_title in files:
            if drive_id in have:
                continue
            path = cr.download(drive_id, folder)
            if path is None:  # too big, a form, or no access: keep it as a link instead
                skipped += 1
                known.append({"drive_id": drive_id, "name": file_title, "path": "", "link_only": True})
            else:
                saved.append(str(path))
                known.append({"drive_id": drive_id, "name": path.name, "path": str(path)})
        with session() as s:
            s.get(CourseItem, item_id).files = known
    if not saved:
        return f"{name}: เก็บเป็นลิงก์ {skipped} ไฟล์" if skipped else None
    actions.record("classroom.files", f"ดาวน์โหลดสื่อ {len(saved)} ไฟล์: {name}", str(folder),
                   source_label="Classroom", undo={"paths": saved})
    return f"สื่อใหม่ {len(saved)} ไฟล์ ({name})" + (f" · เก็บเป็นลิงก์ {skipped}" if skipped else "")


async def _undo_files(undo: dict) -> None:
    for p in undo["paths"]:
        Path(p).unlink(missing_ok=True)


actions.register_undo("classroom.files", _undo_files)


def setup() -> None:
    if fetch not in sync.AFTER_FOLLOWED:
        sync.AFTER_FOLLOWED.append(fetch)
