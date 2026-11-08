# my_secretary

A personal scheduling secretary that sits on top of your Google Calendar. It
helps manage your daily and academic schedule, and — the headline feature —
plans work time backward from your project deadlines based on your actual
progress (read automatically from your git repos / TODO, not just manual entry).

> **Archived.** This was the project's README during v1 (M0–M6; M7 was next, M8 was
> parked). It moved here on 2026-11-08, when v2 replaced it. It describes the code at tag
> `v1-final`, not the code in this tree. The current README is [`../../README.md`](../../README.md).

---

## Status

**M6 — Email intake (read-only)** is done: a new **Mail** page browses/searches the
inbox (free Google API) and **scans** mail with a **local LLM via Ollama**
(`scb10x/llama3.1-typhoon2-8b-instruct`, Thai/English) to extract deadlines/meetings/events
as *suggestions only* — no Claude tokens, and mail bodies never leave the machine. Scan
scope is **Unread** or **Today (all read+unread)**; a scheduler job pre-warms today's scan
each morning. Scans **auto-pin** schedule-worthy items (dated, or deadline/meeting/event) to
the Projects page ("📧 From email" section), and **dated ones are added to your calendar** —
you review and **unpin** anything you don't want (unpin also removes the event). Pinning an
old, never-scanned email triggers a **deeper re-read** to recover its date + a summary. The
secretary can also read mail in chat (`search_email`, `recent_unread_email`). All read-only
(`gmail.readonly`); sending is M7.

**M5 — Proactive engine** is done: the Home page shows a **daily brief** (Claude
writes a short morning summary from your calendar + deadlines, generated once a day
and cached) and **deadline nudges** (overdue / due-soon / replan suggestions,
tokenless). An APScheduler job pre-warms the brief each morning; it also generates
lazily on first open. Nightly replan is **suggest-only** (never edits your calendar).
M0–M4 are complete: calendar plumbing + chat agent, the dashboard, the Google
Classroom academic layer, and the project planner (headline feature; smart planning
is chat-driven).

### Roadmap
- **M0** Foundation: Google OAuth + read/write a calendar event ✓
- **M1** Chat assistant: Claude agent with calendar tools (full CRUD) ✓
- **M2** React dashboard: 3 pages, live calendar + global chat ✓
- **M3** Academic input: **Google Classroom** (courses, assignments + due dates,
  submission status — **not** course materials; on a *separate school account*) ✓
- **M4** Project planner: backward-plan work blocks from deadlines + auto-read
  progress; supplies last-commit + status to the Projects page (deterministic core
  + opt-in Claude reprioritization) ✓
- **M5** Proactive engine: daily brief (Claude, cached daily), deadline nudges, and
  suggest-only nightly replan (APScheduler) ✓
- **M6** Email intake (read-only): Mail page (browse/search), local-LLM schedule
  extraction, email Q&A in chat. Extraction is **offloaded to a local LLM via Ollama**
  (free, private, off the Pro budget); Claude stays for chat + tool use. ✓
- **M7** Email replies (write): draft + send, **always with explicit approval before sending**.
  ← *we are here next*

---

## Web design (the 3-page app)

React Router with a top nav: **Home / Academic / Projects**. The chat is a single
**global floating widget** mounted once at the app shell (bottom-right on every
page) — it is the **same conversation everywhere** and **persists across navigation**
(hidden with CSS when closed, never unmounted, so history survives).

- **Page 1 — Home** (`pages/Home.tsx`): FullCalendar **week** view on top, LIVE
  against the backend (fetches the *visible* range via `fetchEventsRange` →
  `GET /calendar/range`, refetches on navigation). Bottom row is LIVE (M5):
  **☀️ Daily brief** (`GET /brief/today`, with a Refresh button) + **⏰ Deadlines**
  (`GET /nudges`: overdue / due-soon / replan suggestions).
- **Page 2 — Academic** (`pages/Academic.tsx`): LIVE (M3). Top = outstanding
  to-dos split into Overdue / Upcoming / No-deadline (the "keep but separate"
  choice); below = every subject with its assignments, due dates, submission-state
  badges, and live (per-minute) countdowns, sorted by deadline. One fetch of
  `/academic/assignments` feeds both sections.
- **Page 3 — Projects** (`pages/Projects.tsx`): LIVE (M4). **Discover repos** (scan a
  folder), per-project cards (name, last commit, status, deadline, effort), inline
  edit, and **Plan now → preview → "Add to calendar"** (free deterministic, per
  project). Cross-project / constrained planning is done in **chat**, not here.

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
  the **personal** account; **Google Classroom is on a separate
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
    (`claude auth status` → claude.ai / firstParty / your account; no API key set).
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
- **M3 (2026-06-19):** Google Classroom academic integration, end-to-end.
  - **Go/no-go: GREEN** — the school Workspace allows third-party Classroom access
    (read 21 courses / 13 active, 166 assignments).
  - **Dual-account auth** (`services/google_auth.py`): `get_credentials(account, scopes)`
    manages a token file per account (personal→`token.json`, school→`token_school.json`)
    and re-consents when requested scopes grow. `calendar.py` now uses it (account
    "personal"); Classroom uses it (account "school").
  - **Google scope migration gotcha:** Google now hands back
    `classroom.student-submissions.me.readonly` when you request
    `classroom.coursework.me.readonly`, and `oauthlib` crashes on the scope change.
    Fixed with `OAUTHLIB_RELAX_TOKEN_SCOPE=1` + a substitution-aware re-consent check
    (so it doesn't loop). The substituted scope still lists coursework fine.
  - **`services/classroom.py`** (read-only, school account, scopes: courses.readonly,
    coursework.me.readonly, announcements.readonly — **no materials**): `list_courses`,
    `list_assignments` (normalized + `submitted`/`overdue` flags, 5-min TTL cache),
    `list_todo` / `list_todo_grouped` (overdue / upcoming / no_deadline).
  - **`routers/academic.py`**: `GET /academic/{courses,assignments,todo}` (verified 200).
  - **Agent tools** (`agent/classroom_tools.py`): `list_todo`, `list_courses` on a second
    in-process MCP server "classroom"; agent verified answering "what's overdue?".
  - **Academic page** (frontend): to-dos (overdue/upcoming/no-deadline) + per-subject
    assignments with live countdowns. `npm run build` passes.
- **M4 (2026-06-21) — deterministic core done; Claude-on-top still pending.**
  - **Project model** gained `status` (active/waiting/done/dropped), `estimated_hours`,
    `last_commit_at` (`repo_path` already existed). DB recreated (it was empty).
  - **`services/repos.py`** (tokenless git reads): `discover_repos(root)` (one level
    deep), `read_progress(repo_path)` (last commit, counts, recent subjects).
  - **Projects API** (`routers/projects.py`): full CRUD, `POST /projects/discover`
    (upsert repos by path, refresh last-commit, leaves your goal/deadline/effort),
    `GET /projects/{id}/progress`.
  - **`services/planner.py`** — deterministic gap-filler: reads calendar busy
    intervals, places `block_hours` work blocks in free gaps within a daily working
    window, capped per day, before the deadline. Defaults: 09:00–21:00, 1.5h blocks,
    3h/day. Pure (no tokens). `POST /projects/{id}/plan` previews (no writes);
    `POST /projects/{id}/plan/commit` books approved blocks as calendar events.
  - **Projects page** (frontend): Discover button, per-project cards (status, last
    commit, deadline, effort), inline edit, and Plan-now → preview → "Add to calendar".
    `npm run build` passes. Verified backend: 12h → 8×1.5h blocks, 0 unscheduled.
  - **Claude planning is chat-driven** (pivoted from a button, so you can state
    constraints in plain language: "plan project A for next week, mornings only, leave
    project B alone"). `agent/planner_tools.py` gives the secretary two tools —
    `list_projects` (deadlines/remaining hours) and `get_free_slots` (REAL block-sized
    free slots from the deterministic core) — and it books via the existing
    `create_event`/`delete_event`. System prompt: read projects → get real slots →
    honor constraints → on RE-plan, delete that project's existing `Work: <project>`
    blocks first (replace, not stack), never touch projects told to leave alone.
    Because `/chat` is **stateless**, a clear command is carried out in one turn and the
    agent reports what it added/removed. Verified: "plan my_secretary, mornings only,
    leave research_labs alone, don't book yet" → proposed only the real morning slots,
    flagged that 3 of 12h fit, offered to widen the window. (The old button-based
    `/plan/smart` + `smart_planner.py` were removed in favor of this.)
- **M5 (2026-06-21) — proactive engine.**
  - **Daily brief** (`agent/brief.py`): gathers today's calendar + nudges, Claude writes
    a short plain-text brief. Cached one-per-day in the `DailyBrief` table via
    `services/brief_store.get_or_create_today` (lazy on first open; `force` to refresh).
    The one regularly-scheduled token use.
  - **Nudges** (`services/nudges.py`, tokenless): overdue + due-soon (Classroom
    assignments + project deadlines) + suggest-only replan flags for active projects
    due soon with hours left.
  - **Scheduler** (`scheduler.py`, APScheduler `AsyncIOScheduler`): a 07:00 cron job
    pre-warms the brief; started/stopped in the FastAPI lifespan. Nightly replan is
    suggest-only (computed live in nudges), so no calendar-editing job.
  - **API** (`routers/proactive.py`): `GET /brief/today`, `POST /brief/regenerate`,
    `GET /nudges`. **Home page** wired: live BriefCard (+ Refresh) and DeadlinesCard.
    Verified: brief generated once then served from cache; scheduler clean in lifespan.
  - **Ignore (M5+):** old un-submittable homework / dead projects shouldn't nag.
    Assignments: `IgnoredAssignment` table + `services/dismissed.py`; filtered out of
    to-dos, nudges, brief, and the agent's `list_todo` (via a new `exclude_ids` arg on
    `classroom.list_todo[_grouped]`). API: `POST /academic/ignore`,
    `DELETE /academic/ignore/{id}`, `GET /academic/ignored`; `/academic/assignments`
    now carries an `ignored` flag. UI: ✕ "ignore" on each to-do (greyed + "un-ignore"
    in the subject list). Projects: a one-click **Ignore** = status `dropped` (already
    excluded from nudges/planning). Verified: ignore → drops from nudges → un-ignore restores.
- **M6 (2026-06-21) — email intake (read-only) + first local-LLM offload.**
  - **Gmail service** (`services/gmail.py`, `gmail.readonly`, **personal** account):
    `list_unread`, `list_messages(query)` (Gmail search syntax), normalized to
    `{id, from, subject, date, snippet, body, unread, link}` with a light multipart/HTML
    body extractor; 2-min cache. **Shares the personal `token.json`** — so it requests
    the *union* of calendar + gmail scopes (one consent; the calendar, needing only its
    subset, then never re-consents — avoids a token ping-pong). *Re-consent happens once*
    on first Mail use to add the gmail scope.
  - **Local LLM** (`services/local_llm.py`): talks to **Ollama** over HTTP (httpx, no new
    dep). `chat_json()` = JSON-mode, temp 0, serialized behind a lock (one generation at a
    time so the GPU isn't thrashed), defensive JSON parse, clear `OllamaError` on failure.
    Model is config-driven (`OLLAMA_MODEL`, default `scb10x/llama3.1-typhoon2-8b-instruct`).
  - **Extraction** (`services/mail_extract.py`): scans unread mail, one email per local-LLM
    call, returns schedule **suggestions only** (`{type, title, datetime, note, +source}`) —
    nothing is written to the calendar. *Why local:* high-volume, simple, privacy-sensitive →
    free + on-device, keeping the Pro budget for chat.
  - **Chat tools** (`agent/gmail_tools.py`): `search_email`, `recent_unread_email`
    (read-only) registered as a 4th MCP server in the secretary; reading mail in chat is a
    free Google call (only the on-demand scan spends compute, and that's local).
  - **API** (`routers/mail.py`): `GET /mail/unread`, `GET /mail/search`, `POST /mail/scan`,
    `GET /mail/local-status`. **Mail page** (frontend): scan panel (with offline hint),
    Gmail search box, unread list. Verified: backend imports + all 4 routes mounted; frontend
    builds.
  - **M6+ scan-by-date + pins (2026-06-21).** Extended the same milestone:
    - **Scan scope** — `gmail.list_today()` (Gmail `after:today`, read+unread) + `mail_extract.scan(scope)`
      (`unread` | `today`). **Daily auto-scan**: `services/mail_store.py` caches one scan/day in the
      new `DailyMailScan` table (like `DailyBrief`); a 07:10 APScheduler job pre-warms it. The scan
      writes nothing to the calendar — review only (avoids false-positive calendar spam).
    - **Pins** — `PinnedEmail` table + `services/pins.py` (`pin`/`unpin`/`list_pins`/`pinned_ids`).
      Pinning shows the email on the **Projects page** ("📧 From email" section, own card). A **dated**
      pin also creates a calendar event (`calendar.create_all_day_event` for date-only, timed for
      datetimes), id stored so **unpin deletes it**. Calendar writes happen ONLY on an explicit pin,
      never from the daily scan. Idempotent (no duplicate event on re-pin); calendar errors don't
      block the pin.
    - **API** added: `GET /mail/today`, `GET /mail/scan/today`, `POST /mail/scan?scope=`,
      `GET/POST /mail/pins`, `DELETE /mail/pins/{id}`. **UI**: scan + browse scope toggles, 📌 pin
      buttons on suggestions (carry the date → calendar) and on emails (no date), Projects "From
      email" section with unpin + "✓ on calendar". Verified: pin flow (all-day/timed/no-date,
      idempotency, unpin-deletes-event) via mocked calendar; both new tables created; frontend builds.
  - **M6+ DB snapshot cache (2026-06-21) — skim instantly, don't refetch every time.**
    - **`Snapshot` table + `services/cache.py`**: a generic key→JSON store with `fetched_at`.
      `serve(key, fetcher, ttl, refresh, add_task)` does **stale-while-revalidate** — returns the
      cached snapshot immediately, and if older than the TTL schedules a background refresh (FastAPI
      `BackgroundTasks`) so the next visit is fresh. `refresh=true` forces a live fetch;
      `clear_prefix()` invalidates a family of keys. Survives restarts (unlike the in-memory caches).
    - **Applied to** the slow Google reads: `GET /academic/assignments` (TTL 30 min, ignored-flags
      applied on top of the snapshot each call), `GET /mail/unread` + `GET /mail/today` (TTL 10 min),
      and `GET /calendar/range` (TTL 2 min, **per-range** key). Search stays live (ad-hoc).
      All three now return a `{data, fetched_at, stale}` envelope.
    - **Calendar coherence**: every calendar write (`create_event`, `create_all_day_event`,
      `update_event`, `delete_event` — incl. chat-driven ones) calls `cache.clear_prefix("calendar:")`,
      so edits show on the next read instead of waiting out the TTL.
    - **UI**: Academic + Mail show an "updated Nm ago · Refresh" label (`timeAgo`); the calendar
      unwraps the envelope transparently. Verified: cold/fresh/forced/stale-revalidate + prefix
      invalidation unit-tested; backend imports; frontend builds.
  - **M6+ auto-pin + deep-read + page memory (2026-06-21).**
    - **Auto-pin on scan** — `pins.auto_pin_items(items)` pins every schedule-worthy item
      (`_qualifies` = has a date, OR type deadline/meeting/event); dated ones also get a calendar
      event. One pin per email (dated items sort first so the calendar gets the real date). Runs on
      **both** the manual `POST /mail/scan` (offloaded via `anyio.to_thread` so calendar I/O doesn't
      block the loop) **and** the daily `mail_store` scan. The user reviews the "From email" list and
      unpins junk (which deletes the event). `pins.*` now manage their own DB sessions (no `db` param).
    - **Deep re-read on manual pin** — `mail_extract.deep_extract(msg)`: a higher-effort single-email
      read (8k-char body, summary+date prompt). `POST /mail/pins` calls it (via `gmail.get_message`)
      when a pin arrives without a date — so pinning an old, never-scanned email still recovers its
      date + a readable note (and calendars it). Verified live on a Thai email: parsed B.E. 2569 →
      2026-07-15T16:30 with an English summary.
    - **Mail page memory** — a module-level `saved` snapshot restores the page's browse/search/scan
      results after navigating away and back (survives unmount, not a full reload); the initial
      auto-fetch is skipped when state was restored.
    - Verified: `auto_pin_items` (dated→calendar, undated meeting→pinned no-cal, promo `other`→skipped,
      dedupe) via mocked calendar; `deep_extract` live; frontend builds.

---

## Tech stack

- **Backend:** Python (3.14, `uv`) + FastAPI + uvicorn
- **LLM:** Claude via the **Claude Agent SDK** on the Claude **Pro** subscription
  (no paid API; leave `ANTHROPIC_API_KEY` blank). Kept integration-agnostic.
- **Local LLM:** **Ollama** for the email→schedule extraction (M6) — free, private,
  on-GPU. Model in `OLLAMA_MODEL` (default `scb10x/llama3.1-typhoon2-8b-instruct`,
  a Thai/English 8B that fits an 8 GB GPU). `ollama serve` must be running to scan.
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
a chat button (bottom-right, on every page). Academic shows your live Google Classroom
assignments (M3); Projects stays a placeholder until M4. CORS is configured for the
Vite dev origin.

**Classroom (school account) one-time auth:** the Academic page reads from a *separate
school account*. Authorize it once with `uv run python scripts/smoke_classroom.py`
(from `backend/`) and sign in with your **school** account — it caches
`token_school.json`. The personal-account `token.json` is unaffected.

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
2. **APIs & Services → Library →** enable the APIs you use, each individually:
   **Google Calendar API** (M0), **Google Classroom API** (M3), **Gmail API** (M6).
   *Enabling an API and granting OAuth scopes are separate gates* — if a feature 403s
   with `accessNotConfigured`, the API just isn't enabled in the project yet (click
   the link in the error → **Enable** → wait ~1–2 min).
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
