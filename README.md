# my_secretary

A personal secretary that runs on your own computer. It reads your Gmail according to who
sent it, plans your week into Google Calendar, and keeps your projects moving when your
Claude quota runs out. It reports to you on Discord and on a local web page. Everything it
does is logged, and an action that can be undone carries its undo.

> This README is the project's public record: what the secretary does, how it is built,
> how to run it, and how it got here. The planning documents and the day-to-day progress log
> are kept private, so some commit messages name files that are not in this copy.

**Status: v2 (2026-11-08).**
- v2 is a clean rewrite. It was planned on a plan board in three stages (features → look →
  development plan) and built phase by phase from that plan.
- Phases B1–B7 are done and merged.
- B8 (the web page on the iPad through Tailscale) is set aside for now; the iPad uses Discord.
- v1 is kept at tag `v1-final`, and its README is archived in [`docs/v1/README.md`](docs/v1/README.md).

---

## What it does

You reach the secretary in two places. Both are in Thai.

- **A private Discord server.** It works the same from the computer, the iPad or the phone.
  The bot makes five channels:
  - **#คุยกับเลขา:** your questions and commands.
  - **#ด่วน:** mail from important people, appointments it added to your calendar, and
    reminders before appointments and deadlines.
  - **#สรุป:** the morning brief, the evening review and the weekly review.
  - **#อนุมัติ:** plans that need your yes, with buttons.
  - **#ไอเดีย:** ideas you type from any device.
- **A web page** at http://localhost:8000 on this computer. Pages:
  - วันนี้, คนและอีเมล, โปรเจค, งานเบื้องหลัง, ตาราง, ไอเดีย, การใช้เวลา, สมุดกติกา,
    สิ่งที่เลขาทำ, ตั้งค่า;
  - a top bar with the ask box, the bell (everything waiting for you), a theme picker (6
    themes) and จดไอเดีย.

### Mail and people
- **Rounds:** every email is checked, read or not, in a big round at 00:00 and a small one at
  12:00. Important people and keywords are watched every 5 minutes.
- **Three tiers:**
  - **สำคัญ** (important): you're told at once. Each person has an end date and your note
    about why.
  - **สนใจ** (interested): one summary per person per day. First-time senders start here.
  - **ไม่สนใจ** (ignored): subjects only.
- **Appointments:** from important people they go straight into Google Calendar, with a link
  to the email and an undo. From interested people they wait for your yes.
- **Follow-ups:** tasks found in mail, and replies you're waiting for, are tracked until they
  close.
- **Gmail is read-only.**

### Schedule
- **One week:** Google Calendar, Classroom coursework, tasks from mail, projects and your own
  tasks.
- **Work blocks** are planned backwards from deadlines and synced to Google Calendar. They
  respect your rules: hours to avoid, and focus hours filled first.
- **Reminders** go out before appointments and deadlines.
- **Planned vs actual:** each block is compared with what you actually did (from ActivityWatch).

### Briefs and reviews
- **Morning brief at 07:00:** important mail, who sent what, today's appointments, project
  news and what waits for you.
- **Evening review at 21:00:** how the day went against the plan.
- **Weekly review on Sunday at 19:00:**
  - one message per topic: people to renew or move, the schedule, time use, stale projects,
    and idea groups that have grown;
  - each topic says why, what it will do, how, and how far;
  - one button accepts every default.

### Projects and background work
- **Projects:** `~/Projects` is scanned and each project's `PROGRESS.md` is read.
- **Projects send their news (B10):** เชื่อมทุกโปรเจค on the projects page writes a note into
  each project's `CLAUDE.local.md` (hidden from git; the project's own `CLAUDE.md` is left
  alone). It tells Claude Code working there to report finished steps, questions, deadlines and
  automatic runs with the `secretary-news` command, which scripts can call too. The news shows
  on the today and projects pages and in the morning brief
  ([`docs/CONNECT.md`](docs/CONNECT.md)).
- **Continuing stopped work:** when work stops (the quota ran out, or you were interrupted),
  the secretary plans how to continue. Each plan has a risk score, a model and effort, and a
  token budget.
  - Low-risk plans run on their own while more than 70% of the week's quota is left.
  - Everything else asks in #อนุมัติ.
  - The work happens in a git worktree on its own branch, and stops when it runs over budget
    or starts repeating itself.

### Ideas and time use
- **Ideas:** jot one with **Super+I** on the computer, or in #ไอเดีย from any device. Ideas
  are tagged by rules and grouped twice a day. A group that grows can become a project or a
  task.
- **Time use:** ActivityWatch records which window is in front. A privacy blocklist is applied
  twice: before anything is stored, and again when the secretary reads it.
  - Time is sorted into categories and projects by rules.
  - Recording is **off** until you switch it on.

### Ask anything
- **Where:** in #คุยกับเลขา or in the web page's ask box.
- **How it answers:** Sonnet answers quickly from read-only tools over every part of the
  store, with links to the sources. The tools cover:
  - people and mail, and replies you're waiting for;
  - the schedule, tasks and projects;
  - ideas, time use, Classroom and the rules book.
- **ให้ Opus คิดต่อ** hands a question on to Opus.
- **Orders (B9):** an order goes to Opus, and does at most 25 things (Discord's 25 buttons). The
  chat remembers the conversation, so "ทำต่อ" carries on. The action tools it gets cover:
  - tasks and appointments, keeping hours free, replanning;
  - people's tiers, follow-ups, ideas, rules from a sentence;
  - continuing a project, answering what waits for you.

  Each tool calls the function a page button calls, so the action is logged with its undo.
  - The answer lists what was done, with ย้อนกลับ for each.
  - What can't be undone waits for ทำเลย.
  - A request that needs planning gets a plan instead. When you approve it, the secretary
    carries it out, and your own steps become tasks.
  - It never sends anything, deletes, or changes settings.

---

## How it is built

- **One process, local only.** It runs on this computer as a systemd user service listening on
  `127.0.0.1:8000`. One FastAPI process serves the API, the built web page, the Discord bot and
  the clock. The bot connects *out* to Discord, so nothing is opened to the network.
- **Layers, imports pointing down only** (`backend/app/__init__.py`):
  `api/` → `features/` → `connectors/` → `core/`.
- **Claude through the Claude Agent SDK on the Claude Pro subscription**, not the paid API.
  - Each task has a model and an effort, changeable in ตั้งค่า. The defaults:
    - questions in chat: Sonnet, low;
    - ให้ Opus คิดต่อ: Opus, high;
    - planning and commands: Opus, high;
    - reading mail: Opus, medium;
    - background-job plans: Opus, high.
  - Every call is recorded with its tokens.
  - Small jobs (idea tags, window categories, project news) are meant for OmniRoute. It has
    no model yet, so rules and templates do them.
- **A quota watcher** reads what is left of the week's Claude quota. If it can't, every
  background plan asks you first.
- **One table of decisions** holds everything waiting for you. It shows in the bell, on the
  today page and in Discord, and an answer in any one place settles all three.
- **The rules book** holds three kinds of rule:
  - your own rules;
  - the 7 kinds of high-risk work;
  - rules the secretary learned, which wait for your OK.
- **Undo:** every action goes through one log, which keeps what is needed to undo it.
- **The store** is SQLite at `~/.secretary/secretary.db`, outside the repo. Alembic runs the
  migrations, and a daily backup is kept for 14 days.
- **The clock:** a round that has never been switched on starts **off**, and you switch rounds
  on in ตั้งค่า. Rounds missed while the computer was off run when it comes back.

| Round | When | Claude tokens |
|---|---|---|
| เฝ้าคนสำคัญและคีย์เวิร์ด | every 5 minutes | yes (Opus reads the mail) |
| รอบอ่านอีเมล ใหญ่ / เล็ก | 00:00 · 12:00 | yes |
| วางและซิงก์ตาราง | every 15 minutes | no |
| เตือนก่อนถึงกำหนด | every 5 minutes | no |
| ดึงงานและสื่อจาก Classroom | every 2 hours | no |
| สแกนโปรเจคใน ~/Projects | 06:30 | no |
| อ่านข่าวจากโปรเจค | every 5 minutes | no |
| งานเบื้องหลังในโปรเจค | every 15 minutes, 01:00–06:00 | yes, within the quota rules |
| สรุปเช้า · ทบทวนเย็น | 07:00 · 21:00 | no (templates) |
| จัดกลุ่มไอเดีย | 00:05 · 12:05 | no |
| อ่านการใช้เวลาจาก ActivityWatch | every 15 minutes | no |
| ทบทวนรายสัปดาห์ | Sunday 19:00 | no (templates) |
| สำรองฐานข้อมูล | 03:30 (the only round on by default) | no |

**Privacy:**
- Gmail is read-only.
- ActivityWatch's data stays on this computer, and is filtered twice.
- The web page listens on 127.0.0.1 only.
- Secrets live in `backend/.env`, and the Google tokens in `~/.secretary/google/` (mode 0600).
  None of them can be committed.

---

## Running it

**Always on** (details in [`docs/setup/always-on.md`](docs/setup/always-on.md)):
```bash
./deploy/install.sh                        # uv sync, build the web page, install and start the service
systemctl --user restart my-secretary      # after new backend code or a change to backend/.env
journalctl --user -u my-secretary -f       # its log
```
The service serves `frontend/dist` from this folder, so `npm run build` changes the live page
at once. Backend code changes need a restart; the web page shows a banner while the running
code is older than the code on disk.

**Development:**
```bash
cd backend && uv run uvicorn app.main:app --reload --port 8001   # a second instance next to the service
cd frontend && npm run dev                                       # http://localhost:5173, its /api goes to the service on :8000
cd backend && uv run pytest                                      # 445 tests
```
A second process gets the web page and the API only. The clock and the Discord bot stay with
whichever process started first (`~/.secretary/worker.lock`), so a question is never answered
twice.

For experiments that write data, use a scratch store *and* an empty bot token:
`SECRETARY_DATA_DIR=/tmp/scratch SECRETARY_DISCORD_TOKEN= uv run uvicorn app.main:app --port 8001`.
The lock lives inside the store. A scratch store therefore doesn't see the real one's lock, and
would otherwise start a second bot with the real token.

---

## Setup (one time)

1. **Packages:** `cd backend && uv sync`, then `cd frontend && npm install && npm run build`.
2. **Claude:** log in to the `claude` CLI with your Claude Pro account (`claude auth status`).
   No API key: the secretary runs on the subscription.
3. **Google:**
   1. In Google Cloud, enable the Gmail, Calendar, Classroom and Drive APIs.
   2. Create an OAuth client of type *Desktop app*, and save it as `backend/credentials.json`.
   3. Connect each account once (it opens your browser):
      `cd backend && uv run python -m app.connectors.google connect gmail`. Use `ku` for the
      university account, which also reads Classroom.
4. **Discord:** a private server and a bot, in [`docs/setup/discord.md`](docs/setup/discord.md).
5. **Always on:** [`docs/setup/always-on.md`](docs/setup/always-on.md).
6. **Ideas and time use:** the Super+I key and ActivityWatch, in
   [`docs/setup/ideas-and-time.md`](docs/setup/ideas-and-time.md).
7. **Projects' news:** `/usr/bin/python3 desktop/secretary_news.py install` puts the
   `secretary-news` command in `~/.local/bin`. Then press เชื่อมทุกโปรเจค on the projects page.
8. **Rounds:** switch on the ones you want in ตั้งค่า.

**Configuration (`backend/.env`):** every key starts with `SECRETARY_`, so v1's keys in the
same file are ignored.

| Key | Default | What it is |
|---|---|---|
| `SECRETARY_DATA_DIR` | `~/.secretary` | everything the secretary writes: the store, backups, Google tokens, the project inbox, worktrees |
| `SECRETARY_TIMEZONE` | `Asia/Bangkok` | |
| `SECRETARY_PROJECTS_DIR` | `~/Projects` | the projects it scans |
| `SECRETARY_DISCORD_TOKEN` · `_GUILD_ID` · `_OWNER_ID` | empty | the bot, your server, and you (the only person it listens to); empty keeps the bot off |
| `SECRETARY_WEB_URL` | `http://localhost:8000` | where the links the bot posts point |
| `SECRETARY_GOOGLE_CLIENT_FILE` | `backend/credentials.json` | the OAuth client |

Your preferences (models and effort, the theme, reminder times, which rounds run) live in the
store, and change from ตั้งค่า while the secretary runs.

> 🔒 `.env`, `credentials.json`, `token*.json` and `*.db` are git-ignored. Never commit them.

---

## Code layout

```
backend/app/
  main.py        the FastAPI app: API, the built web page, the Discord bot, the clock
  api/           one router per page
  features/      mail · schedule · classroom · briefs · projects · jobs · ideas · time · weekly · ask
  connectors/    google (sign-in) · gmail · gcal · classroom · discord_bot · activitywatch
  core/          db · tables · clock · llm · actions · rules · settings · backup · config
backend/migrations/   Alembic
backend/tests/        pytest
frontend/src/         React: pages/, components/ (the shell, the bell, the ask box), themes.css
desktop/              the Super+I popup and its key, the ActivityWatch installer
deploy/               install.sh · uninstall.sh · the systemd user unit
docs/                 setup/ (guides), CONNECT.md, map/ and reference-map/ (interactive maps), v1/
```

---

## Progress log

**v2** (each phase was planned in chat, built one commit per step on its own branch, checked by
the user, then merged into `v2` with `--no-ff`). The full record of every phase (the answers,
the decisions, and what each commit holds) is kept in a private build log.

- **Planning (2026-11-04 → 05).** The user's handwritten feature list became `feature.md`.
  The plan board then covered:
  - features (13 features and 12 proposals);
  - the look (a mockup of every screen, 6 themes);
  - the development plan (phases B1–B8, code layout, data model, decisions).

  It was exported to a plan document, which is kept private.
- **B1 foundation** (2026-11-05, `62ed55e`):
  - the store, the clock, and the action log with undo;
  - the Claude caller (model and effort per task, tokens recorded);
  - the Discord bot, and the web page's shell with themes;
  - the systemd service and the daily backup.
- **B2 mail and people** (2026-11-05, `efa6f9d`):
  - three tiers with end dates and notes;
  - the 5-minute watch, and the 00:00 and 12:00 rounds;
  - appointments into Calendar, tasks from mail, follow-ups;
  - the people page.
- **B3 schedule** (2026-11-06, `34389e8`):
  - planning backwards from deadlines, synced with Google Calendar;
  - Classroom coursework and materials;
  - reminders, and the schedule page.
- **B4 briefs and today** (2026-11-06, `2d92d55`): the morning and evening briefs, the
  decisions gathered in one place, and the today page.
- **B5 projects and background work** (2026-11-06, `6118cc7`):
  - the project registry, project news and the project inbox;
  - the quota watcher, risk rules, budgets and the stopper;
  - worktrees, #อนุมัติ, and the rules book.
- **B6 ideas and time** (2026-11-08, `056a4ee`):
  - the Super+I popup and #ไอเดีย, with rule tags and groups;
  - ActivityWatch behind the blocklist, categories, and planned vs actual.
- **B7 weekly review and ask anything** (2026-11-08, `aaf0698`):
  - the weekly review with one message per topic and accept-all;
  - weekly people proposals;
  - hours to avoid and focus hours in the planner;
  - nine read-only tools for asking.
- **B8 iPad:** set aside on 2026-11-08; the iPad uses Discord.
- **v2 merged into `main`** on 2026-11-08 and tagged `v2.0`.

**v1** (2026-06 → 11, tag `v1-final`). M0–M6 were done:
- the calendar and the chat agent;
- the dashboard;
- Google Classroom;
- the deadline planner;
- the daily brief;
- read-only mail with a local LLM.

M7 (mail replies) was not built. M8 (a 3D character companion) is parked and is not part of
this copy. Details are in [`docs/v1/README.md`](docs/v1/README.md). There is also an
interactive map, `docs/reference-map/`, of how 15 similar open-source projects are designed. It is a snapshot from 4 November 2026; where it points to `docs/map/`, it means the v1 map, which is kept at tag `v1-final`.

---

## Tech stack

- **Backend:** Python ≥ 3.12 with `uv` · FastAPI + uvicorn · SQLAlchemy 2 + Alembic + SQLite ·
  APScheduler 3 · discord.py · the Claude Agent SDK · the Google API client.
- **Frontend:** React 19 · Vite · TypeScript · Tailwind 4 · React Router · FullCalendar.
- **Desktop:** a GTK 4 popup for Super+I · ActivityWatch (awatcher) with a GNOME Shell
  extension for the focused window.

Built with help from AI coding assistants.
