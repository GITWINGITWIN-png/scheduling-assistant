# my_secretary

A personal scheduling secretary that sits on top of your Google Calendar. It
helps manage your daily and academic schedule, and — the headline feature —
plans work time backward from your project deadlines based on your actual
progress.

## Status

**M0 — Foundation** (in progress): a FastAPI backend that authenticates to
Google Calendar and can read/write events. This proves the riskiest plumbing
before we build the chat agent, the React dashboard, and the planner.

### Roadmap
- **M0** Foundation: Google OAuth + read/write a calendar event ← *we are here*
- **M1** Chat assistant: Claude agent with calendar tools
- **M2** React dashboard: calendar view + chat + project list
- **M3** Academic input: **Google Classroom** (course names, assignments + due dates,
  submission status, announcements — **not** course materials; on a *separate school
  account*) as the primary source; recurring classes + syllabus PDF as fallback.
  Course materials are reserved for a future, separate study/learning-manager project.
- **M4** Project planner: backward-plan work blocks from deadlines + progress
- **M5** Proactive engine: daily brief, deadline nudges, nightly replan
- **M6** Email intake (read-only): extract schedule items, inbox triage, email Q&A
- **M7** Email replies (write): draft + send, always with explicit approval before sending

## Tech stack

- **Backend:** Python + FastAPI
- **LLM:** Claude via the **Claude Agent SDK**, authenticated with the user's Claude Pro
  subscription (avoids paid API). LLM layer kept integration-agnostic so it can fall back
  to the Anthropic API if needed.
- **Calendar:** Google Calendar API
- **Email:** Gmail API (read-only scope for M6; send/compose scope added at M7) — same
  Google OAuth as the calendar
- **Academic:** Google Classroom API (read-only) on a **separate school Google account**.
  The app therefore handles two Google logins (personal: calendar/gmail; school:
  classroom), via an account-scoped credential loader. Subject to the school's Workspace
  admin permitting third-party app access — if blocked, fall back to Classroom calendar
  sync or manual entry.
- **DB:** SQLite + SQLAlchemy (the "smart layer")
- **Scheduler:** APScheduler (proactive jobs)
- **Frontend:** React + Vite + FullCalendar (added at M2)

---

## Setup

### 1. Install dependencies

This project uses [uv](https://docs.astral.sh/uv/). From `backend/`:

```bash
cd backend
uv sync
```

### 2. Google Calendar credentials (one-time)

The app needs its own identity with Google so it can run independently.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and
   create a project (or pick an existing one).
2. **APIs & Services → Library →** enable the **Google Calendar API**.
3. **APIs & Services → OAuth consent screen:** choose *External*, fill in the
   basics, and under *Test users* add your own Google account.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID →**
   application type **Desktop app**.
5. Download the JSON and save it as `backend/credentials.json`.

### 3. Configure

```bash
cp .env.example .env       # from inside backend/
```

Then edit `backend/.env` and set your `ANTHROPIC_API_KEY`. The Google paths
already point at `credentials.json` / `token.json` by default.

### 4. Run

```bash
uv run uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs**. The first time you call `/calendar/upcoming`
a browser window opens asking you to authorize access — approve it, and a
`token.json` is cached so future runs are silent.

### Smoke test
- `GET /calendar/upcoming?days=7` → lists your next week of events.
- `POST /calendar/events` → creates an event (try a test one).

> 🔒 `.env`, `credentials.json`, and `token.json` are git-ignored. Never commit them.
