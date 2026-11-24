"""Sorting time into categories and projects by rules (4.1, B6). There's no model until OmniRoute is
connected (the user's choice at the B6 plan); what the rules can't place is "Other", and you can
place it yourself on the time page, which makes a rule of yours.

The order (the first rule that matches decides):
1. yours: "app or title has X -> category Y (and project Z)", made on the time page;
2. a project named in the title, as registered on the projects page: VS Code says
   "file - my_secretary - Visual Studio Code", a terminal "~/Projects/my_secretary", a browser
   "my_secretary | GitHub". It counts as Code / project, or as Study when the project holds a
   Classroom course's folder. The longest name wins, so "datacom-report" beats "datacom";
3. an editor or a terminal: Code, without a project (before the title words below, so a terminal
   in ~/.secretary/inbox isn't mail);
4. a meeting (Meet, Zoom, Teams);
5. studying (Classroom, a course's name, Moodle, Coursera...);
6. mail and chat (Gmail, Thunderbird, Discord, Slack...);
7. a browser: Web and social;
8. anything else: Other.
Matching works the same way as the privacy filter: case never matters, latin words stand alone,
and Thai is found inside words.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select

from app.core import actions, settings
from app.core.db import session
from app.features.time import privacy
from app.features.time.tables import Activity

CATEGORIES = {"code": "โค้ด / โปรเจค", "study": "เรียน", "meeting": "ประชุม", "chat": "อีเมลและแชท",
              "web": "เว็บและโซเชียล", "other": "อื่นๆ"}
RULES_KEY = "time.categories"  # yours: [{"field": "app"|"title", "match": "...", "category": "...", "project": ""}]

MEETING_APPS = ("zoom", "teams", "webex", "skype")
MEETING_TITLES = ("google meet", "meet -", "zoom meeting", "zoom workplace", "microsoft teams", "webex")
STUDY_TITLES = ("google classroom", "classroom", "moodle", "coursera", "edx", "udemy", "khan academy", "lecture", "บทเรียน")
CHAT_APPS = ("thunderbird", "evolution", "geary", "mailspring", "discord", "slack", "telegram", "telegramdesktop", "signal",
             "element")
CHAT_TITLES = ("gmail", "inbox", "outlook", "proton mail", "discord", "slack", "telegram")
CODE_APPS = ("code", "code-oss", "vscodium", "cursor", "zed", "sublime_text", "nvim", "gvim", "emacs", "kate", "pycharm",
             "jetbrains", "idea", "gnome-terminal-server", "ptyxis", "kitty", "alacritty", "konsole", "wezterm", "foot",
             "tilix", "terminator", "console", "kgx", "xterm", "ghostty")
BROWSERS = ("firefox", "google-chrome", "chromium", "brave-browser", "microsoft-edge", "epiphany", "vivaldi", "opera", "zen",
            "librewolf")


def _any(values, text: str) -> bool:
    return any(privacy.found(v, text) for v in values)


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", s.lower()).strip()


class Sorter:
    """One per read: what the rules need, loaded once."""

    def __init__(self) -> None:
        from app.features.classroom.tables import Course
        from app.features.projects.tables import Project

        with session() as s:
            projects = s.execute(select(Project.id, Project.name, Project.path)
                                 .where(Project.hidden.is_(False), Project.missing.is_(False))).all()
            courses = s.execute(select(Course.name, Course.folder).where(Course.state.in_(("followed", "ended")))).all()
        folders = [Path(f).expanduser() for _, f in courses if f]
        self.projects = sorted(((pid, name, any(_inside(f, Path(path)) for f in folders)) for pid, name, path in projects
                                if len(_norm(name)) >= 3), key=lambda p: -len(_norm(p[1])))
        self.courses = tuple(n for n, _ in courses if n and len(n) >= 3)
        self.yours = list(settings.get(RULES_KEY, []) or [])
        self.ids = {name: pid for pid, name, _ in self.projects}

    def project_in(self, title: str) -> tuple[int, str, bool] | None:
        norm = _norm(title)
        for pid, name, course in self.projects:  # the longest name first
            n = _norm(name)
            left = r"(?<![a-z0-9])" if re.match(r"[a-z0-9]", n) else ""
            right = r"(?![a-z0-9])" if re.search(r"[a-z0-9]$", n) else ""
            if re.search(left + re.escape(n) + right, norm):
                return pid, name, course
        return None

    def sort(self, app: str, title: str) -> tuple[str, int | None, str]:
        """-> (category, project id, project name)."""
        a = app.lower()
        for r in self.yours:
            if privacy.found(r["match"], app if r.get("field") == "app" else title):
                name = r.get("project") or ""
                return r["category"], self.ids.get(name), name
        if (hit := self.project_in(title)) is not None:
            pid, name, course = hit
            return ("study" if course else "code"), pid, name
        if _any(CODE_APPS, a):
            return "code", None, ""
        if _any(MEETING_APPS, a) or _any(MEETING_TITLES, title):
            return "meeting", None, ""
        if _any(STUDY_TITLES, title) or _any(self.courses, title):
            return "study", None, ""
        if _any(CHAT_APPS, a) or _any(CHAT_TITLES, title):
            return "chat", None, ""
        if _any(BROWSERS, a):
            return "web", None, ""
        return "other", None, ""


def _inside(folder: Path, project: Path) -> bool:
    try:
        return folder.resolve().is_relative_to(project.resolve())
    except (OSError, ValueError):
        return False


def resort() -> int:
    """Sort everything kept again (after you add a rule, or new projects). -> rows changed."""
    sorter = Sorter()
    n = 0
    with session() as s:
        for row in s.scalars(select(Activity)):
            new = sorter.sort(row.app, row.title)
            if new != (row.category, row.project_id, row.project):
                row.category, row.project_id, row.project = new
                n += 1
    return n


def yours() -> list[dict]:
    return list(settings.get(RULES_KEY, []) or [])


def add_rule(field: str, match: str, category: str, project: str = "", *, via: tuple[str, str] = ("หน้าเว็บ", "")) -> int:
    """"app or title has X -> category Y" (from the time page's Other list). -> action id."""
    if field not in ("app", "title") or category not in CATEGORIES:
        raise ValueError("เลือกว่าดูจากแอปหรือชื่อหน้าต่าง และหมวด")
    match = privacy.clean(match)
    if len(match) < 2:
        raise ValueError("สั้นเกินไป")
    same = lambda r: r["field"] == field and r["match"] == match  # noqa: E731
    replaced = next((r for r in yours() if same(r)), None)
    rules = [r for r in yours() if not same(r)]
    rules.insert(0, {"field": field, "match": match, "category": category, "project": project.strip()})
    settings.put(RULES_KEY, rules)
    changed = resort()
    return actions.record("time.category", f"จัดหมวด: {match} → {CATEGORIES[category]}", f"จัดใหม่ {changed} ช่วง",
                          source_label=via[0], source_url=via[1], undo={"field": field, "match": match, "replaced": replaced})


async def _undo_rule(undo: dict) -> None:
    """Take back only this rule (rules added after it stay), and the one it replaced comes back."""
    rules = [r for r in yours() if not (r["field"] == undo["field"] and r["match"] == undo["match"])]
    if undo.get("replaced"):
        rules.insert(0, undo["replaced"])
    settings.put(RULES_KEY, rules)
    resort()


actions.register_undo("time.category", _undo_rule)
