"""Google Classroom (read-only) and the Drive download for its materials, on the KU account.

Each call asks only for the permission it uses, so listing coursework works even before
the materials / Drive permissions are granted (see google.credentials).
Synchronous, like gmail.py: call through asyncio.to_thread.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, time, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from app.connectors import google
from app.core.config import get_config

# A submission in one of these states is handled: turned in, or graded and returned.
SUBMITTED = {"TURNED_IN", "RETURNED"}
# Google's own formats can't be downloaded as they are; they are exported to PDF.
EXPORT_PDF = {"application/vnd.google-apps.document", "application/vnd.google-apps.presentation",
              "application/vnd.google-apps.spreadsheet", "application/vnd.google-apps.drawing"}
MAX_BYTES = 200 * 1024 * 1024  # bigger files are linked, not downloaded


def _classroom(*need: str):
    return build("classroom", "v1", credentials=google.credentials(google.CLASSROOM_ACCOUNT, *need), cache_discovery=False)


def _paged(request, key: str, limit: int | None = None) -> list[dict]:
    """Every page of a list call (request(page_token) builds one), or the first `limit` items."""
    items, token = [], None
    while True:
        r = request(token).execute()
        items += r.get(key, [])
        token = r.get("nextPageToken")
        if not token or (limit and len(items) >= limit):
            return items[:limit] if limit else items


def courses() -> list[dict]:
    svc = _classroom(google.CLASSROOM[0])
    return _paged(lambda t: svc.courses().list(courseStates=["ACTIVE"], pageSize=100, pageToken=t), "courses")


def coursework(course_id: str, limit: int | None = None) -> list[dict]:
    """Assignments, newest change first (limit=1: just the latest, to see if the course is busy)."""
    svc = _classroom(google.CLASSROOM[1])
    return _paged(lambda t: svc.courses().courseWork().list(courseId=course_id, orderBy="updateTime desc",
                                                            pageSize=limit or 100, pageToken=t), "courseWork", limit)


def submissions(course_id: str) -> dict[str, str]:
    """{coursework id: your submission state} for every assignment in the course."""
    svc = _classroom(google.CLASSROOM[1])
    subs = _paged(lambda t: svc.courses().courseWork().studentSubmissions().list(
        courseId=course_id, courseWorkId="-", userId="me", pageSize=100, pageToken=t), "studentSubmissions")
    return {s["courseWorkId"]: s.get("state", "NEW") for s in subs}


def materials(course_id: str, limit: int | None = None) -> list[dict]:
    """Course materials (the "เนื้อหา" posts), newest change first."""
    svc = _classroom(google.CLASSROOM_MATERIALS)
    return _paged(lambda t: svc.courses().courseWorkMaterials().list(courseId=course_id, orderBy="updateTime desc",
                                                                     pageSize=limit or 100, pageToken=t),
                  "courseWorkMaterial", limit)


def announcements(course_id: str, limit: int | None = None) -> list[dict]:
    svc = _classroom(google.CLASSROOM[2])
    return _paged(lambda t: svc.courses().announcements().list(courseId=course_id, orderBy="updateTime desc",
                                                               pageSize=limit or 100, pageToken=t), "announcements", limit)


def due_at(cw: dict) -> datetime | None:
    """Classroom splits the due time into dueDate + dueTime (UTC). A date without a time means
    the end of that day, here 23:59 your time."""
    d = cw.get("dueDate")
    if not d:
        return None
    t = cw.get("dueTime")
    if t is None:
        return datetime.combine(datetime(d["year"], d["month"], d["day"]).date(), time(23, 59), get_config().tz)
    return datetime(d["year"], d["month"], d["day"], t.get("hours", 0), t.get("minutes", 0), tzinfo=timezone.utc)


def stamp(item: dict) -> datetime | None:
    """When a coursework / material / announcement was last changed."""
    value = item.get("updateTime") or item.get("creationTime")
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


# ------------------------------------------------------------------ Drive: a material's file
def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip() or "ไฟล์"


def _free_path(folder: Path, name: str) -> Path:
    """`name` in `folder`, or "name (2).ext" if that is taken: never overwrite a file."""
    path = folder / name
    n = 2
    while path.exists():
        path = folder / f"{Path(name).stem} ({n}){Path(name).suffix}"
        n += 1
    return path


def download(file_id: str, folder: Path) -> Path | None:
    """Save one Drive file into `folder`. Google Docs/Slides/Sheets become PDFs.
    -> the saved path, or None if it's too big or can't be read (then it stays a link)."""
    svc = build("drive", "v3", credentials=google.credentials(google.CLASSROOM_ACCOUNT, google.DRIVE_READ),
                cache_discovery=False)
    try:
        meta = svc.files().get(fileId=file_id, fields="name,mimeType,size").execute()
    except HttpError as exc:
        if exc.resp.status in (403, 404):
            return None
        raise
    name, mime = _safe(meta["name"]), meta["mimeType"]
    if mime in EXPORT_PDF:
        request, name = svc.files().export_media(fileId=file_id, mimeType="application/pdf"), f"{Path(name).stem}.pdf"
    elif mime.startswith("application/vnd.google-apps"):
        return None  # forms, sites, folders: links only
    elif int(meta.get("size", 0)) > MAX_BYTES:
        return None
    else:
        request = svc.files().get_media(fileId=file_id)
    folder.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    path = _free_path(folder, name)
    path.write_bytes(buf.getvalue())
    return path
