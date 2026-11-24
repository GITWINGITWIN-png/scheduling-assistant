# my_secretary

A personal secretary that runs on one computer and talks to its owner in Thai, through a private Discord server and a local web page. It sorts Gmail by who sent it, plans the week into Google Calendar around deadlines, writes a morning brief and an evening review, and continues stopped coding work in the owner's projects when the Claude quota allows. Every action is logged, and an action that can be undone keeps what it needs to undo it.

The current version is v2, a rewrite finished on 8 November 2026 (tag `v2.0`). v1 is kept at tag `v1-final`, and its README is in [docs/v1/README.md](docs/v1/README.md). The planning documents and the day-to-day progress log stay private, so a few commit messages name files that are not in this repo.

## What it does

- It checks every email twice a day and watches important senders every 5 minutes. Senders sit in three tiers. Mail from important people is reported at once, and their appointments go straight into Google Calendar with an undo; appointments from other senders wait for approval. Gmail access is read-only.
- It plans Google Calendar events, Classroom coursework, tasks found in mail and project deadlines into work blocks, counting back from each deadline and keeping the hours the owner has blocked.
- It sends a morning brief at 07:00, an evening review at 21:00 and a weekly review on Sunday evening, with one message per topic and a button that accepts every default.
- It reads each project's `PROGRESS.md`, collects the news that projects send with the `secretary-news` command, and plans how to continue work that stopped. Low-risk plans run on their own in a git worktree while more than 70% of the week's quota is left; the rest wait for approval in Discord.
- It answers questions from read-only tools over everything it stores, with links to the sources. Orders go through the same functions as the page buttons, so each change is logged with its undo, and an order never sends mail, deletes anything or changes settings.

The full feature list is in [docs/features.md](docs/features.md).

## How it is built

One FastAPI process, run as a systemd user service on `127.0.0.1:8000`, serves the API, the built React page, the Discord bot and the scheduler. The bot connects out to Discord, so no port is opened to the network. The backend is layered `api/ → features/ → connectors/ → core/`, and imports only point down.

The secretary calls Claude through the Claude Agent SDK on a Claude Pro subscription, not the paid API. Each task has its own model and effort, and every call is recorded with its tokens. Data lives in SQLite at `~/.secretary/secretary.db`, outside the repo, with Alembic migrations and a daily backup kept for 14 days.

Details are in [docs/architecture.md](docs/architecture.md), and the build history is in [docs/history.md](docs/history.md).

## Running it

Setup needs a Google Cloud OAuth client, a Discord bot and a logged-in `claude` CLI. The steps are in [docs/setup/install.md](docs/setup/install.md).

```bash
./deploy/install.sh                       # install packages, build the page, start the service
systemctl --user restart my-secretary     # after backend changes or a change to backend/.env
journalctl --user -u my-secretary -f      # follow the log
cd backend && uv run pytest               # run the tests
```

## Tech stack

Python 3.12 with uv, FastAPI, SQLAlchemy 2 and Alembic on SQLite, APScheduler, discord.py, the Claude Agent SDK and the Google API client. The front end uses React 19, Vite, TypeScript, Tailwind 4, React Router and FullCalendar. On the desktop, a small GTK 4 popup takes quick notes and ActivityWatch records which window is in front.
