"""The ideas round (12:00 and 00:00, D6 ③), and what a grown group becomes (P11).

Each round, rules only (the user's choice at the B6 plan, until OmniRoute is connected):
1. takes in what the Super+I popup kept while the secretary was down;
2. tags the ideas nobody tagged yet ("", or the rules found nothing last time), with the same
   rules as the suggestions: #tags, project names, the tags you already use;
3. puts every tagged idea in the group of its first non-project tag, and makes the group when
   it's new (a group is one tag, its name starts as the tag);
4. proposes the groups that have grown to GROWN ideas, once: a card in #Ideas (D6 ④) and a
   "Things waiting for your decision" (the bell, the today page, the ideas page):
   - Open project: a folder ~/Projects/<name> with a README.md and a PROGRESS.md built from the
     group's ideas (no model), on the projects page as Idea (the user's choice, 4.a);
   - Make it a task: one task with the ideas as its details, which the planner books time for;
   - Not yet: asked again when the group has AGAIN_AFTER more ideas.

A round with nothing new says nothing (no card, no log line).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select

from app.core import actions
from app.core.config import get_config
from app.core.db import now, session
from app.core.tables import Decision, Task
from app.core.timefmt import thai_date
from app.features.ideas import store
from app.features.ideas.tables import SOURCES, Idea, IdeaGroup

log = logging.getLogger(__name__)

GROWN = 4  # ideas before a group is proposed (the plan: "e.g. 4 ideas or more", accepted at the B6 plan)
AGAIN_AFTER = 2  # "not yet": proposed again once it has this many more

# Called after a round with something to tell: (Round). cards.py posts the D6 cards.
POSTED: list[Callable[["Round"], Awaitable[None]]] = []


@dataclass
class Round:
    placed: list[tuple[int, int]] = field(default_factory=list)  # (idea id, group id), grouped this round
    asked: list[tuple[int, int]] = field(default_factory=list)  # (group id, decision id), proposed this round
    left: int = 0  # ideas still without a group (no tag found)

    def line(self) -> str | None:
        if not (self.placed or self.asked):
            return None
        parts = [f"เข้ากลุ่ม {len(self.placed)} ไอเดีย"] if self.placed else []
        if self.asked:
            parts.append(f"กลุ่มที่โตพอ {len(self.asked)}")
        if self.left:
            parts.append(f"ยังไม่มีแท็ก {self.left}")
        return " · ".join(parts)


def size(s, group_id: int) -> int:
    return s.scalar(select(func.count()).select_from(Idea).where(Idea.group_id == group_id)) or 0


# ------------------------------------------------------------------ 1–3: tag and place
def tag_untagged() -> int:
    """Rule tags for the ideas nobody tagged (and the ones the rules found nothing for before:
    there may be a new project or tag now). Your own tags are never touched. -> how many got some."""
    projects, known = store.project_tags(), store.vocabulary()
    n = 0
    with session() as s:
        for idea in s.scalars(select(Idea).where((Idea.tagged == "") | ((Idea.tagged == "rules") & (Idea.group_id.is_(None))))):
            tags = store.suggest(idea.text, projects=projects, known=known)
            if tags != idea.tags or idea.tagged == "":
                n += bool(tags)
                idea.tags, idea.tagged = tags, "rules"
    return n


def place(only: list[int] | None = None) -> list[tuple[int, int]]:
    """Put tagged ideas that have no group yet into their group. -> [(idea id, group id)]."""
    projects, sizes = store.project_tags(), store.group_sizes()
    out = []
    with session() as s:
        q = select(Idea).where(Idea.group_id.is_(None)).order_by(Idea.created_at)
        if only is not None:
            q = q.where(Idea.id.in_(only))
        for idea in s.scalars(q).all():
            tag = store.primary(idea.tags or [], projects, sizes)
            if tag is None:
                continue
            g = s.scalar(select(IdeaGroup).where(IdeaGroup.tag == tag))
            if g is None:
                g = IdeaGroup(tag=tag, name=tag)
                s.add(g)
                s.flush()
            idea.group_id, idea.grouped_at = g.id, now()
            sizes[tag] = sizes.get(tag, 0) + 1  # the next idea of this round sees it grow
            out.append((idea.id, g.id))
    return out


# ------------------------------------------------------------------ 4: propose
def ripe() -> list[int]:
    """Groups that have grown enough and aren't waiting, done, or told "not yet" lately."""
    with session() as s:
        out = []
        for g in s.scalars(select(IdeaGroup).where(IdeaGroup.status.in_(("open", "later")))):
            n = size(s, g.id)
            if n >= GROWN and (g.status == "open" or n >= g.asked_size + AGAIN_AFTER):
                out.append(g.id)
        return out


def propose(group_id: int) -> int:
    """Ask once: a "Things waiting for your decision" of kind "idea". -> the decision id."""
    with session() as s:
        g = s.get(IdeaGroup, group_id)
        n = size(s, g.id)
        about = about_project(s, g.id)
        d = Decision(kind="idea", title=g.name, detail={"group_id": g.id, "size": n, "tag": g.tag, "project": about or ""})
        s.add(d)
        s.flush()
        g.status, g.asked_size, g.decision_id = "asked", n, d.id
        return d.id


def about_project(s, group_id: int) -> str | None:
    """The project its ideas name most ("about finance"), if any."""
    projects = store.project_tags()
    count: dict[str, int] = {}
    for tags in s.scalars(select(Idea.tags).where(Idea.group_id == group_id)):
        for t in tags or []:
            if t in projects:
                count[t] = count.get(t, 0) + 1
    return projects[max(count, key=count.get)] if count else None


async def run() -> str | None:
    """The "ideas" round (00:05 and 12:05)."""
    store.import_outbox()
    tag_untagged()
    result = Round(placed=place())
    result.asked = [(gid, propose(gid)) for gid in ripe()]
    with session() as s:
        result.left = s.scalar(select(func.count()).select_from(Idea).where(Idea.group_id.is_(None))) or 0
    if result.placed or result.asked:
        for hook in POSTED:
            try:
                await hook(result)
            except Exception:
                log.exception("the ideas round's cards couldn't be posted")
    return result.line()


# ------------------------------------------------------------------ the answers (P11)
class AnswerError(ValueError):
    """Why an answer can't be done, in your words."""


def _waiting(s, group_id: int) -> IdeaGroup:
    g = s.get(IdeaGroup, group_id)
    if g is None:
        raise AnswerError("ไม่พบกลุ่มนี้")
    if g.status in ("project", "task"):
        raise AnswerError(f"กลุ่มนี้{'เป็นโปรเจค' if g.status == 'project' else 'เป็นงาน'}ไปแล้ว")
    return g


def _settle(s, g: IdeaGroup, status: str, answer: str) -> None:
    if g.decision_id and (d := s.get(Decision, g.decision_id)) is not None and d.status == "pending":
        d.status, d.answer, d.answered_at = status, answer, now()


def ideas_of(group_id: int) -> list[Idea]:
    with session() as s:
        rows = s.scalars(select(Idea).where(Idea.group_id == group_id).order_by(Idea.created_at)).all()
        s.expunge_all()
        return list(rows)


def _bullets(ideas: list[Idea]) -> str:
    return "\n".join(f"- {' '.join(i.text.split())} ({SOURCES.get(i.source, i.source)}, {thai_date(i.created_at)})" for i in ideas)


FOLDER = re.compile(r"^[^/\\\x00]{1,80}$")


def folder_name(name: str) -> str:
    """The folder you typed, checked: no "/", not hidden, not "." or "..", not taken."""
    name = " ".join(name.split())
    if not name or not FOLDER.match(name) or name.startswith(".") or name in (".", ".."):
        raise AnswerError("ชื่อโฟลเดอร์ใช้ไม่ได้ · ห้ามว่าง ห้ามมี / และห้ามขึ้นต้นด้วยจุด")
    if (get_config().projects_dir / name).exists():
        raise AnswerError(f"มีโฟลเดอร์ ~/Projects/{name} อยู่แล้ว · ตั้งชื่ออื่น")
    return name


def suggested_folder(group_id: int) -> str:
    """What the name box starts with: the group's tag, as a folder name."""
    with session() as s:
        g = s.get(IdeaGroup, group_id)
        base = re.sub(r"[^\w฀-๿.-]+", "-", g.tag if g else "idea").strip("-.") or "idea"
    name, n = base, 2
    while (get_config().projects_dir / name).exists():
        name, n = f"{base}-{n}", n + 1
    return name


def open_project(group_id: int, name: str, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[int, int]:
    """Open project: the folder, its README.md and PROGRESS.md, on the projects page. -> (project id, action id)."""
    from app.features.projects.tables import DEFAULT_POTENTIAL, DEFAULT_URGENCY, Project

    name = folder_name(name)
    with session() as s:
        g = _waiting(s, group_id)
        title, n = g.name, size(s, g.id)
    ideas = ideas_of(group_id)
    folder: Path = get_config().projects_dir / name
    folder.mkdir(parents=True)
    today = thai_date(now())
    (folder / "README.md").write_text(
        f"# {name}\n\nเปิดจากกลุ่มไอเดีย “{title}” ({n} ไอเดีย) ในเลขา เมื่อ {today}\n\n"
        f"## ไอเดียตั้งต้น\n\n{_bullets(ideas)}\n\n## เป้าหมาย\n\n- (เขียนว่าโปรเจคนี้จะทำให้ได้อะไร)\n", encoding="utf-8")
    steps = "\n".join(f"- [ ] ลองไอเดีย: {' '.join(i.text.split())[:120]}" for i in ideas)
    (folder / "PROGRESS.md").write_text(
        f"# PROGRESS\n\n## ตอนนี้: เริ่มจากไอเดีย (เลขาเปิดให้เมื่อ {today})\n\n"
        f"- [ ] เขียนเป้าหมายใน README.md\n{steps}\n", encoding="utf-8")
    from app.features.projects import progress

    with session() as s:  # registered now, so the next scan doesn't ask "set a new project level" about it
        p = Project(name=name, path=str(folder), status="idea", potential=DEFAULT_POTENTIAL, urgency=DEFAULT_URGENCY,
                    first_seen=now(), scanned_at=now(), last_activity=now(), progress=progress.read(folder))
        s.add(p)
        s.flush()
        g = s.get(IdeaGroup, group_id)
        g.status, g.project_id = "project", p.id
        _settle(s, g, "approved", "project")
        project_id = p.id
    action_id = actions.record("idea.project", f"เปิดโปรเจคจากกลุ่มไอเดีย: {title}", f"~/Projects/{name}",
                               source_label=via[0], source_url=via[1])
    return project_id, action_id


def make_task(group_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> tuple[int, int]:
    """Make it a task: one task in the schedule, the ideas as its details. -> (task id, action id)."""
    with session() as s:
        g = _waiting(s, group_id)
        title, about = g.name, about_project(s, g.id)
    ideas = ideas_of(group_id)
    with session() as s:
        task = Task(title=title, source="idea", source_ref=str(group_id), project=about or "",
                    details=f"จากกลุ่มไอเดีย “{title}”:\n{_bullets(ideas)}"[:5000])
        s.add(task)
        s.flush()
        g = s.get(IdeaGroup, group_id)
        old = g.status
        g.status, g.task_id = "task", task.id
        _settle(s, g, "approved", "task")
        task_id = task.id
    action_id = actions.record("idea.task", f"ทำกลุ่มไอเดียเป็นงาน: {title}", "เลขาจะหาเวลาในตารางให้",
                               source_label=via[0], source_url=via[1],
                               undo={"group_id": group_id, "task_id": task_id, "status": old})
    return task_id, action_id


def later(group_id: int, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """Not yet: not now; asked again when it has grown by AGAIN_AFTER. -> action id."""
    with session() as s:
        g = _waiting(s, group_id)
        old = (g.status, g.asked_size)
        g.status, g.asked_size = "later", size(s, g.id)
        _settle(s, g, "rejected", "later")
        title = g.name
    return actions.record("idea.later", f"กลุ่มไอเดียยังไม่ทำ: {title}", f"ถามใหม่เมื่อมีเพิ่มอีก {AGAIN_AFTER} ไอเดีย",
                          source_label=via[0], source_url=via[1],
                          undo={"group_id": group_id, "status": old[0], "asked_size": old[1]})


def rename(group_id: int, name: str, *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    name = " ".join(name.split())[:120]
    if not name:
        raise AnswerError("ตั้งชื่อกลุ่มก่อน")
    with session() as s:
        g = s.get(IdeaGroup, group_id)
        if g is None:
            raise AnswerError("ไม่พบกลุ่มนี้")
        old, g.name = g.name, name
        if g.decision_id and (d := s.get(Decision, g.decision_id)) is not None and d.status == "pending":
            d.title = name
    return actions.record("idea.rename", f"ตั้งชื่อกลุ่มไอเดีย: {name}", f"เดิม “{old}”", source_label=via[0], source_url=via[1],
                          undo={"group_id": group_id, "name": old})


def _reopen(s, g: IdeaGroup) -> None:
    """Back to waiting for your answer (after an undo)."""
    if g.decision_id and (d := s.get(Decision, g.decision_id)) is not None:
        d.status, d.answer, d.answered_at = "pending", "", None
        g.status = "asked"
    else:
        g.status = "open"


async def _undo_task(undo: dict) -> None:
    with session() as s:
        if (task := s.get(Task, undo["task_id"])) is not None and task.status == "open":
            task.status = "dropped"
        if (g := s.get(IdeaGroup, undo["group_id"])) is not None:
            g.task_id = None
            _reopen(s, g)


async def _undo_later(undo: dict) -> None:
    with session() as s:
        if (g := s.get(IdeaGroup, undo["group_id"])) is not None:
            g.asked_size = undo["asked_size"]
            _reopen(s, g)


async def _undo_rename(undo: dict) -> None:
    with session() as s:
        if (g := s.get(IdeaGroup, undo["group_id"])) is not None:
            g.name = undo["name"]


actions.register_undo("idea.task", _undo_task)
actions.register_undo("idea.later", _undo_later)
actions.register_undo("idea.rename", _undo_rename)


def setup() -> None:
    from app.core import clock
    clock.attach("ideas", run)
