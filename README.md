# my_secretary

A personal scheduling secretary that sits on top of your Google Calendar. It
helps manage your daily and academic schedule, and — the headline feature —
plans work time backward from your project deadlines based on your actual
progress (read automatically from your git repos / TODO, not just manual entry).

> This README is the project's canonical record: roadmap, web design,
> architecture decisions, important constraints, and a progress log all live here.

---

## Status

**M2 — Dashboard** is done: a 3-page React app (Home / Academic / Projects) with a
live Google Calendar and a global chat assistant, talking to a FastAPI backend.
M0 (Google Calendar plumbing) and M1 (the Claude chat agent with full calendar
CRUD) are complete.

### Roadmap
- **M0** Foundation: Google OAuth + read/write a calendar event ✓
- **M1** Chat assistant: Claude agent with calendar tools (full CRUD) ✓
- **M2** React dashboard: 3 pages, live calendar + global chat ✓ ← *we are here*
- **M3** Academic input: **Google Classroom** (course names, assignments + due dates,
  submission status, announcements — **not** course materials; on a *separate school
  account*) as the primary source; recurring classes + syllabus PDF as fallback.
  Requires a **dual-account auth refactor** (see Architecture).
- **M4** Project planner: backward-plan work blocks from deadlines + auto-read progress.
  Also supplies last-commit date + status to the Projects page.
- **M5** Proactive engine: daily brief, deadline nudges, nightly replan (APScheduler).
- **M6** Email intake (read-only): extract schedule items, inbox triage, email Q&A.
- **M7** Email replies (write): draft + send, **always with explicit approval before sending**.

---

## Web design (the 3-page app)

React Router with a top nav: **Home / Academic / Projects**. The chat is a single
**global floating widget** mounted once at the app shell (bottom-right on every
page) — it is the **same conversation everywhere** and **persists across navigation**
(hidden with CSS when closed, never unmounted, so history survives).

- **Page 1 — Home** (`pages/Home.tsx`): FullCalendar **week** view on top, LIVE
  against the backend. It fetches exactly the *visible* range via
  `fetchEventsRange` → `GET /calendar/range`, and refetches when you navigate
  weeks/months. Bottom row: **Daily brief** (placeholder, M5) + **Deadlines per
  subject** (placeholder, M3).
- **Page 2 — Academic** (`pages/Academic.tsx`): top = "suggested to-dos across all
  subjects" (prioritized, agent-generated); below = every subject with its
  assignments + due dates + live countdowns, sorted by deadline. All placeholder
  until M3 (Google Classroom + agent reasoning).
- **Page 3 — Projects** (`pages/Projects.tsx`): an index of projects — name, last
  commit date, short description, status (unfinished / finished / waiting-for /
  dropped). Reads `GET /projects` (returns `[]` for now). Placeholder until M4
  (the repo-reader supplies last-commit; the Project model still needs a `status`
  field + last-commit).

**LIVE in M2** = Home calendar + global chat. Everything else is a styled
placeholder/empty state shaped for drop-in data later.

**Frontend layout:**
```
frontend/src/
  main.tsx            # BrowserRouter wrapper
  App.tsx             # shell: top nav + Routes + one global <FloatingChat/>
  api.ts              # backend client: sendChat, fetchEventsRange, fetchProjects
  components/
    Chat.tsx          # ChatPanel (scrollable, auto-scrolls) + FloatingChat (global)
    Placeholder.tsx   # reusable empty-state card
  pages/
    Home.tsx  Academic.tsx  Projects.tsx
```

---

## Architecture & key decisions

- **Claude via the Claude Agent SDK on the Pro subscription — NOT the paid API.**
  The user has Claude Pro and wants to avoid metered Anthropic API billing (Pro and
  API credits are billed separately). The whole reasoning layer (chat, calendar
  tool-calling, M4 planning, repo-progress reading) runs on the Agent SDK
  authenticated with the same login as Claude Code. **Leave `ANTHROPIC_API_KEY`
  blank** so it uses the Pro login. Keep proactive jobs modest (one daily brief, one
  nightly replan) to stay under Pro's rolling caps. The LLM layer is kept
  integration-agnostic (CalendarService/DB don't depend on it) so it could fall back
  to the paid API later if Pro limits/reliability ever demand it.
- **Calendar is always the Google Calendar API; SQLite is always the brain.**
  Events live in Google Calendar; the "smart layer" (projects, progress, plans)
  lives in SQLite via SQLAlchemy.
- **Two Google accounts (dual-account auth, needed for M3).** Calendar + Gmail are on
  the **personal** account (you@example.com); **Google Classroom is on a separate
  school account**. M0 used a single `token.json`; M3 must generalize this into an
  **account-scoped credential loader** (e.g. `token_personal.json` +
  `token_school.json`, each with its own scopes), one Cloud project / OAuth client,
  two authorizing accounts.
  - **Go/no-go risk:** the school likely uses Google Workspace for Education; the admin
    may block third-party/unverified apps from Classroom — *unfixable in code*. The
    OAuth attempt on the school account IS the test. If blocked, fall back to Classroom
    calendar-sync (due dates → a Google Calendar we read) or manual/syllabus entry.
    A go/no-go probe lives at `backend/scripts/test_school_classroom.py` (not yet run).
- **Least privilege on scopes.** Classroom is read-only and **course materials are
  intentionally EXCLUDED** (do NOT request `classroom.courseworkmaterials.*`).
  Rationale: a *separate future study/learning-manager project* will own materials and
  get its own access — scheduling and studying are separate concerns.
- **Email is split by trust level.** M6 = read-only (`gmail.readonly`) for extraction /
  triage / Q&A. M7 = write (`gmail.compose` / `gmail.send`) for replies, which
  **always draft for explicit approval before sending** — never autonomous (outward-facing
  and hard to undo).
- **Secrets are git-ignored and must never be committed:** `.env`, `credentials.json`,
  `token*.json`, `*.db`.

**Backend layout:**
```
backend/app/
  main.py             # FastAPI app: CORS (allow :5173) + routers
  routers/            # calendar.py, chat.py, projects.py
  services/
    calendar.py       # Google Calendar: list/create/update(patch)/delete + _rfc3339 helper
  agent/
    tools.py          # CalendarService wrapped as in-process SDK MCP tools (CRUD)
    secretary.py      # ask(prompt): Agent SDK options, system prompt, allowed tools
backend/scripts/      # chat.py (REPL), smoke_agent.py, test_school_classroom.py
```

---

## Progress log

- **M0 + M1 (2026-06-19):** scaffold + chat agent built and verified end-to-end.
  - Confirmed the Agent SDK reaches Claude on the **Pro login** programmatically
    (`claude auth status` → claude.ai / firstParty / you@example.com; no API key set).
  - Gotcha: the Calendar API wasn't enabled in the Cloud project (403
    `accessNotConfigured`) — enabling it fixed the "500 after OAuth" error.
  - Switched off deprecated `datetime.utcnow()` → tz-aware UTC + `_rfc3339()` helper.
  - Standalone scripts need `sys.path.insert(0, .../backend)` (Python puts `scripts/`
    on the path, not the project root) — added to `scripts/chat.py`.
  - Calendar CRUD verified (create → update(patch) → delete a throwaway event).
    `list_events` includes event ids so the agent can target updates/deletes; the
    system prompt tells it to look up the id first and confirm before deleting.
  - Mutations currently run with `permission_mode="bypassPermissions"` (our own tools);
    a real confirmation gate is deferred to the UI / planned for email send (M7).
  - On GitHub: `git@github.com:GITWINGITWIN-png/my_secretary.git` (repo root; secrets
    git-ignored).
- **M2 (2026-06-19):** `frontend/` = Vite + React 19 + TS + Tailwind v4 (via
  `@tailwindcss/vite`, `@import "tailwindcss"` — no `tailwind.config`) + React Router v7
  + FullCalendar v6. Backend added `CORSMiddleware` (allow :5173) + `GET /projects` (→ `[]`).
  `npm run build` passes (tsc clean).
  - **Three reported bugs fixed:** (1) empty calendar — was fetching the wrong window;
    added `GET /calendar/range` + FullCalendar's visible-range events-function.
    (2) chat couldn't scroll / overflowed — fixed the flex height chain with `min-h-0`
    and added auto-scroll to the newest message. (3) chat reset on navigation — made it
    a single global `FloatingChat` mounted in `App` (hidden, not unmounted).
  - Verified `/calendar/range` returns the user's real events (±30-day window → 4 events).

---

## Tech stack

- **Backend:** Python (3.14, `uv`) + FastAPI + uvicorn
- **LLM:** Claude via the **Claude Agent SDK** on the Claude **Pro** subscription
  (no paid API; leave `ANTHROPIC_API_KEY` blank). Kept integration-agnostic.
- **Calendar:** Google Calendar API
- **Email:** Gmail API (read-only at M6; compose/send at M7) — same OAuth as calendar
- **Academic:** Google Classroom API (read-only) on a **separate school account**
- **DB:** SQLite + SQLAlchemy 2.0 (the "smart layer")
- **Scheduler:** APScheduler (proactive jobs)
- **Frontend:** React 19 + Vite + TypeScript + Tailwind v4 + FullCalendar v6 + React Router v7

---

## Running the app

Two servers, side by side.

**Backend** (from `backend/`):
```bash
uv run uvicorn app.main:app --reload      # http://localhost:8000
```

**Frontend** (from `frontend/`):
```bash
npm install        # first time only
npm run dev        # http://localhost:5173
```

Open **http://localhost:5173**. Home shows your live Google Calendar (week view) and
a chat button (bottom-right, on every page). Academic and Projects are styled
placeholders until M3/M4. CORS is configured for the Vite dev origin.

---

## Setup (one-time)

### 1. Install dependencies
This project uses [uv](https://docs.astral.sh/uv/). From `backend/`:
```bash
cd backend
uv sync
```

### 2. Google credentials
The app needs its own identity with Google so it can run independently.
1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project.
2. **APIs & Services → Library →** enable the **Google Calendar API**.
3. **APIs & Services → OAuth consent screen:** *External*, fill in the basics, add your
   Google account under *Test users*.
4. **Credentials → Create Credentials → OAuth client ID →** application type **Desktop app**.
5. Download the JSON and save it as `backend/credentials.json`.

### 3. Configure
```bash
cp .env.example .env       # from inside backend/
```
**Leave `ANTHROPIC_API_KEY` blank** — the Agent SDK uses your Claude Pro login instead
of the paid API. The Google paths already point at `credentials.json` / `token.json`.

### 4. Run & authorize
```bash
uv run uvicorn app.main:app --reload
```
The first time you hit a calendar endpoint, a browser window opens asking you to
authorize access — approve it, and a `token.json` is cached so future runs are silent.
You can also explore the API at **http://127.0.0.1:8000/docs**.

> 🔒 `.env`, `credentials.json`, `token*.json`, and `*.db` are git-ignored. Never commit them.
