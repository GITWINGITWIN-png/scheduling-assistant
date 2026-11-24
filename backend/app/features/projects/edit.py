"""Change what a project's row says: status, potential, urgency, hidden, let the secretary keep going.

Used by the projects page (W3) and, without the last two, by orders in the chat (B9).
Every change is recorded in What the secretary did and can be undone.
"""

from __future__ import annotations

from app.core import actions
from app.core.db import session
from app.features.projects import scan
from app.features.projects.tables import POTENTIALS, STATUSES, Project

WORDS = {"status": "สถานะ", "potential": "potential", "urgency": "ความเร่งด่วน", "hidden": "ซ่อน", "allow_jobs": "ให้เลขาทำต่อได้"}


class EditError(ValueError):
    """The change can't be made. `code` is the HTTP status the page gets (400 · 404 · 409)."""

    def __init__(self, message: str, code: int = 400) -> None:
        super().__init__(message)
        self.code = code


def edit(project_id: int, changes: dict, *, via: tuple[str, str] = ("หน้าโปรเจค", "")) -> int:
    """Apply `changes` (keys from WORDS) to one project. -> action id."""
    if not changes:
        raise EditError("ไม่มีอะไรให้แก้")
    if unknown := set(changes) - set(WORDS):
        raise EditError(f"แก้ไม่ได้: {', '.join(sorted(unknown))}")
    if changes.get("status", "active") not in STATUSES or changes.get("potential", "C") not in POTENTIALS \
            or not 0 <= changes.get("urgency", 0) <= 5:
        raise EditError("สถานะ potential S–F หรือความเร่งด่วน 0–5 ไม่ถูกต้อง")
    with session() as s:
        p = s.get(Project, project_id)
        if p is None:
            raise EditError("ไม่พบโปรเจคนี้", 404)
        if changes.get("allow_jobs"):
            if scan.is_self(p.path):
                raise EditError("เลขาไม่ทำงานเบื้องหลังในโค้ดของตัวเอง", 409)
            if not p.is_git:
                raise EditError("โปรเจคนี้ยังไม่มี git · เลขาทำงานบน branch แยก จึงต้องมี git ก่อน", 409)
        old = {k: getattr(p, k) for k in changes}
        for k, v in changes.items():
            setattr(p, k, v)
        if "potential" in changes or "urgency" in changes:
            p.level_set = True
        name = p.name
    what = " · ".join(f"{WORDS[k]} {STATUSES.get(v, v) if k == 'status' else ('เปิด' if v is True else 'ปิด' if v is False else v)}"
                      for k, v in changes.items())
    return actions.record("project.edit", f"แก้โปรเจค {name}", what, source_label=via[0], source_url=via[1],
                          undo={"project_id": project_id, "old": old})


async def _undo_edit(undo: dict) -> None:
    with session() as s:
        if p := s.get(Project, undo["project_id"]):
            for k, v in undo["old"].items():
                setattr(p, k, v)


actions.register_undo("project.edit", _undo_edit)
