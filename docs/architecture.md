# Architecture

## One local process

The secretary runs on one computer as a systemd user service listening on `127.0.0.1:8000`. One FastAPI process serves the API, the built web page, the Discord bot and the clock. The bot connects out to Discord, so nothing is opened to the network.

The backend is layered, and imports only point down (`backend/app/__init__.py` checks this):

```
api/ → features/ → connectors/ → core/
```

## Claude

The secretary calls Claude through the Claude Agent SDK on the Claude Pro subscription, not the paid API. Each task has a model and an effort, which can be changed in ตั้งค่า (settings). The defaults:

| Task | Model | Effort |
|---|---|---|
| questions in chat | Sonnet | low |
| ให้ Opus คิดต่อ (let Opus think further) | Opus | high |
| planning and orders | Opus | high |
| reading mail | Opus | medium |
| background-work plans | Opus | high |

Every call is recorded with its tokens. Small jobs (idea tags, window categories, project news) are meant for OmniRoute, which has no model yet, so rules and templates do them for now.

A quota watcher reads what is left of the week's Claude quota. If it cannot read it, every background plan asks first.

## Decisions, rules and undo

One table holds every decision waiting for you. It shows in the bell, on the today page and in Discord, and an answer in any one of them settles all three.

The rules book holds three kinds of rule: your own rules, the 7 kinds of high-risk work, and rules the secretary learned, which wait for your OK.

Every action goes through one log, which keeps what is needed to undo it.

## Storage

The store is SQLite at `~/.secretary/secretary.db`, outside the repo. Alembic runs the migrations, and a daily backup is kept for 14 days.

## The clock

A round that has never been switched on starts off; you switch rounds on in ตั้งค่า. Rounds missed while the computer was off run when it comes back. The Thai round names are the ones shown in settings.

| Round | When | Uses Claude |
|---|---|---|
| เฝ้าคนสำคัญและคีย์เวิร์ด (watch important people and keywords) | every 5 minutes | yes, Opus reads the mail |
| รอบอ่านอีเมล ใหญ่ / เล็ก (big and small mail rounds) | 00:00 and 12:00 | yes |
| วางและซิงก์ตาราง (plan and sync the schedule) | every 15 minutes | no |
| เตือนก่อนถึงกำหนด (reminders before deadlines) | every 5 minutes | no |
| ดึงงานและสื่อจาก Classroom (fetch Classroom work and materials) | every 2 hours | no |
| สแกนโปรเจคใน ~/Projects (scan ~/Projects) | 06:30 | no |
| อ่านข่าวจากโปรเจค (read project news) | every 5 minutes | no |
| งานเบื้องหลังในโปรเจค (background work in projects) | every 15 minutes, 01:00 to 06:00 | yes, within the quota rules |
| สรุปเช้า / ทบทวนเย็น (morning brief, evening review) | 07:00 and 21:00 | no, templates |
| จัดกลุ่มไอเดีย (group ideas) | 00:05 and 12:05 | no |
| อ่านการใช้เวลาจาก ActivityWatch (read time use) | every 15 minutes | no |
| ทบทวนรายสัปดาห์ (weekly review) | Sunday 19:00 | no, templates |
| สำรองฐานข้อมูล (back up the store) | 03:30, the only round on by default | no |

## Privacy

Gmail is read-only. ActivityWatch's data stays on this computer and is filtered twice. The web page listens on 127.0.0.1 only. Secrets live in `backend/.env`, and the Google tokens in `~/.secretary/google/` with mode 0600; git ignores all of them.

## Code layout

```
backend/app/
  main.py        the FastAPI app: API, the built web page, the Discord bot, the clock
  api/           one router per page
  features/      mail, schedule, classroom, briefs, projects, jobs, ideas, time, weekly, ask
  connectors/    google (sign-in), gmail, gcal, classroom, discord_bot, activitywatch
  core/          db, tables, clock, llm, actions, rules, settings, backup, config
backend/migrations/   Alembic
backend/tests/        pytest
frontend/src/         React: pages/, components/ (the shell, the bell, the ask box), themes.css
desktop/              the Super+I popup and its key, the ActivityWatch installer
deploy/               install.sh, uninstall.sh and the systemd user unit
docs/                 setup guides, CONNECT.md, features, this file, history, v1/
```
