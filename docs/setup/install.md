# Install and run

## One-time setup

1. Packages: `cd backend && uv sync`, then `cd frontend && npm install && npm run build`.
2. Claude: log in to the `claude` CLI with a Claude Pro account (`claude auth status` shows it). There is no API key; the secretary runs on the subscription.
3. Google:
   1. In Google Cloud, enable the Gmail, Calendar, Classroom and Drive APIs.
   2. Create an OAuth client of type Desktop app and save it as `backend/credentials.json`.
   3. Connect each account once; it opens your browser: `cd backend && uv run python -m app.connectors.google connect gmail`. Use `ku` instead of `gmail` for the university account, which also reads Classroom.
4. Discord: a private server and a bot, as described in [discord.md](discord.md).
5. Always on: see [always-on.md](always-on.md).
6. Ideas and time use: the Super+I key and ActivityWatch, in [ideas-and-time.md](ideas-and-time.md).
7. Project news: `/usr/bin/python3 desktop/secretary_news.py install` puts the `secretary-news` command in `~/.local/bin`. Then press เชื่อมทุกโปรเจค (connect every project) on the projects page.
8. Rounds: switch on the ones you want in ตั้งค่า (settings).

## Configuration

`backend/.env` holds the settings. Every key starts with `SECRETARY_`, so v1's keys in the same file are ignored.

| Key | Default | Meaning |
|---|---|---|
| `SECRETARY_DATA_DIR` | `~/.secretary` | everything the secretary writes: the store, backups, Google tokens, the project inbox and worktrees |
| `SECRETARY_TIMEZONE` | `Asia/Bangkok` | |
| `SECRETARY_PROJECTS_DIR` | `~/Projects` | the projects it scans |
| `SECRETARY_DISCORD_TOKEN`, `SECRETARY_DISCORD_GUILD_ID`, `SECRETARY_DISCORD_OWNER_ID` | empty | the bot, your server, and you (the only person it listens to); an empty token keeps the bot off |
| `SECRETARY_WEB_URL` | `http://localhost:8000` | where the links the bot posts point |
| `SECRETARY_GOOGLE_CLIENT_FILE` | `backend/credentials.json` | the OAuth client |

Preferences such as models and effort, the theme, reminder times and which rounds run live in the store, and change from ตั้งค่า while the secretary runs.

`.env`, `credentials.json`, `token*.json` and `*.db` are ignored by git and must never be committed.

## Always on

```bash
./deploy/install.sh                        # uv sync, build the web page, install and start the service
systemctl --user restart my-secretary      # after new backend code or a change to backend/.env
journalctl --user -u my-secretary -f       # its log
```

The service serves `frontend/dist` from this folder, so `npm run build` changes the live page at once. Backend changes need a restart; the web page shows a banner while the running code is older than the code on disk.

## Development

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8001   # a second instance next to the service
cd frontend && npm run dev                                       # http://localhost:5173; its /api goes to the service on :8000
cd backend && uv run pytest                                      # the tests
```

A second process gets the web page and the API only. The clock and the Discord bot stay with whichever process started first (`~/.secretary/worker.lock`), so a question is never answered twice.

For experiments that write data, use a scratch store and an empty bot token:

```bash
SECRETARY_DATA_DIR=/tmp/scratch SECRETARY_DISCORD_TOKEN= uv run uvicorn app.main:app --port 8001
```

The lock lives inside the store, so a scratch store does not see the real store's lock and would otherwise start a second bot with the real token.
