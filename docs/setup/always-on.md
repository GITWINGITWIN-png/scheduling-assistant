# Keep the secretary running all the time on this machine (systemd user service)

Secretary v2 runs as a **systemd user service** named `my-secretary`:

- It starts automatically when the machine boots. Linger is already enabled on this machine, so you do not have to log in first.
- If it crashes, it restarts itself within 5 seconds.
- Logs are stored in the system journal.

A single process runs everything: the web page (http://localhost:8000), the secretary clock (นาฬิกาเลขา), and the Discord bot.

## Before installing: things you need to know

- **If this machine has run v1**, the v1 service is replaced, because it uses the same name (`my-secretary`).
  - `install.sh` saves the old service file to `~/.config/systemd/user/my-secretary.service.v1.bak` before overwriting it.
  - This machine has had v2 installed in place of v1 since B1.
- **v2 is only open to this machine** (`127.0.0.1`).
  - v1 was open to every network (`0.0.0.0`), including the LAN.
  - Access from an iPad over Tailscale (B8) is on hold for now. For the moment, the iPad uses Discord.
  - If you want to open it to every network like v1, install with `HOST=0.0.0.0 ./deploy/install.sh`. This is not recommended, because anyone on the same network could ask the secretary and use your Claude quota.

## Install or update

```bash
cd ~/Projects/my_secretary
./deploy/install.sh
```

The script does 4 things, and you can run it again every time after `git pull`:

1. `uv sync --frozen` installs the Python packages listed in `backend/uv.lock`.
2. `npm ci && npm run build` builds the web page.
3. It writes the service file to `~/.config/systemd/user/my-secretary.service`.
4. `enable` (start on boot) and `restart`.

Then the script waits for `/api/health` to respond.

## Common commands

| What you want to know or do | Command |
|---|---|
| Is it running? | `systemctl --user status my-secretary` |
| Watch the live log (Ctrl+C to exit) | `journalctl --user -u my-secretary -f` |
| View the last 100 lines of the log | `journalctl --user -u my-secretary -n 100` |
| View the log since this boot | `journalctl --user -u my-secretary -b` |
| Restart, for example after editing `backend/.env` | `systemctl --user restart my-secretary` |
| Stop temporarily (it starts again on the next boot) | `systemctl --user stop my-secretary` |
| Disable permanently (it does not start on boot) | `systemctl --user disable --now my-secretary` |
| Remove everything (data is not lost) | `./deploy/uninstall.sh` |
| Check that it starts on boot without logging in | `loginctl show-user $USER -p Linger` should return `Linger=yes` (if not, use `loginctl enable-linger $USER`) |

**How to read the status:**

- `Active: active (running)` = running
- `activating (auto-restart)` = it just crashed and is restarting. Check the log to see why it crashed.

## Things that run automatically on a schedule

As per your rules, the secretary tells you every time something new starts running on its own.

| Run | Time | What it touches | How to turn it off |
|---|---|---|---|
| Database backup | Daily at 03:30 (if the machine was off, it runs as soon as it starts) | Writes files to `~/.secretary/backups/` and keeps the latest 14 files | Switch in หน้าตั้งค่า (settings page); or disable the whole service |
| Email watch (B2) | Every 5 minutes | Reads senders and subjects in Gmail (read only). Opus reads only emails from important people, keywords, or emails you are waiting on. Posts to #ด่วน (urgent). Adds calendar entries for important people (reversible) | Switch in หน้าตั้งค่า |
| Large email pass (B2) | 00:00 | Opus reads emails from people you are interested in, grouped per person, and subjects from senders you are not interested in. Requests meetings in #อนุมัติ (approval). Does not post to #สรุป (summary) since B4, because the morning summary now tells you instead | Switch in หน้าตั้งค่า |
| Small email pass (B2) | 12:00 | Same as the large pass, but does not read subjects from senders you are not interested in. Reminds you about pending items in #ด่วน | Switch in หน้าตั้งค่า |
| Schedule planning and sync (B3) | Every 15 minutes | Reads the main calendar (read only) and the “เลขา” (secretary) calendar. Places new work blocks only when something changes. Writes only to the “เลขา” calendar. Does not use a model | Switch in หน้าตั้งค่า; or delete the whole “เลขา” calendar in Google Calendar |
| Deadline reminders (B3) | Every 5 minutes | Posts to #ด่วน before one-time appointments and deadlines, 1 day and 1 hour ahead (does not remind you about weekly recurring appointments). Does not use a model | Switch in หน้าตั้งค่า; or untick it in the schedule rules (กติกาตาราง) |
| Fetch assignments and materials from Classroom (B3) | Every 2 hours | Reads Classroom for the KU account. For tracked courses, assignments with due dates go into the task list, and new materials are downloaded to the course folder. New courses are asked about in #อนุมัติ. Does not use a model | Switch in หน้าตั้งค่า |
| Morning summary (B4) | 07:00 (if the machine was off: sent on startup if it is not yet noon) | Reads only what the secretary has already stored. Posts to #สรุป once a day. Keeps a copy for the today page (หน้าวันนี้). Does not use a model | Switch in หน้าตั้งค่า |
| Evening review (B4, B6) | 21:00 (if the machine was off: sent on startup if it is not yet midnight) | How many schedule blocks were completed, which blocks were missed, actual time today (when activity logging is on), tasks closed, tomorrow, and the runs planned for tonight. The “ย้ายไปพรุ่งนี้” (move to tomorrow) button changes the schedule only when you press it. Posts to #สรุป once a day. Does not use a model | Switch in หน้าตั้งค่า |
| Scan projects (B5) | 06:30 | Reads the folders in `~/Projects` (git log and PROGRESS.md, read only). The first run quietly records them at C.2. New folders after that are asked about in #อนุมัติ. Does not use a model | Switch in หน้าตั้งค่า; or hide folders on the หน้าโปรเจค (projects page) |
| Read project updates (B5) | Every 5 minutes | Reads JSON files in `~/.secretary/inbox/<โปรเจค>/` (following the CONNECT.md guide), then moves them to `read/` or `bad/`. Failed jobs or questions from important projects are posted to #ด่วน. Does not use a model | Switch in หน้าตั้งค่า |
| Background project work (B5) | Every 15 minutes, 01:00 to 06:00 | Only for projects you turned on “ให้เลขาทำต่อได้” (let the secretary keep working). Opus plans from PROGRESS.md (read only). After passing the rules, Claude Code keeps working in a worktree on the branch `secretary/<โปรเจค>` (one per project; each next task builds on the previous one). It can commit. It does not push, does not touch main, and does not touch your folder. If it exceeds its budget, it keeps looping until 06:00 or until you press stop, then stops by itself. Uses your Claude quota | Switch in หน้าตั้งค่า; turn off “ให้เลขาทำต่อได้” one project at a time; turn off self-running in สมุดกติกา (rules notebook), where every plan asks first; stop button (ปุ่มหยุด) on the หน้างานเบื้องหลัง (background work page) |
| Group ideas (B6) | 00:05 and 12:05 | Ideas without a tag get tagged by the rules (#แท็ก (tag), the project name, and tags you have used before), then grouped by tag. Groups that reach 4 ideas are asked about in #ไอเดีย (ideas), and a bell asks whether to open a project, turn it into a task, or wait (asked only once). Does not use a model. Creates nothing on its own until you press a button | Switch in หน้าตั้งค่า; the “จัดกลุ่มเลย” (group now) button on the หน้าไอเดีย (ideas page) runs it once, even when the schedule is off |
| Read time usage from ActivityWatch (B6) | Every 15 minutes (at :10, :25, :40, :55) | Reads ActivityWatch on this machine (read only) for the periods when you were at the computer. Filters out the apps, websites, and windows on the block list, hides names containing blocked words, and skips periods when recording was paused. Stores results in `activity`. For finished schedule blocks, it records done or missed (missed time goes back so the planning run can schedule again). Does not use a model. The recorder itself (awatcher) is a separate systemd user service | The “บันทึกกิจกรรม” (activity logging) switch on the หน้าการใช้เวลา (time usage page) turns off both the recorder and this run |
| Weekly review (B7) | Sunday 19:00 (if the machine was off: sent on startup if it is not yet Monday 12:00) | A weekly overview with one message per topic in #สรุป: people who are close to expiring, and uninterested senders who sent things matching your interests. Schedule rules (focus blocks, repeatedly missed blocks). Time missing from the plan. Quiet projects. Idea groups. Changes nothing until you press a button. Uses templates and does not use a model (the project summary task uses tokens only when you press “รับทั้งสองอย่าง” (accept both)) | Switch in หน้าตั้งค่า; “ส่งตอนนี้” (send now) runs it once, even when the schedule is off |

**Runs for new periods always start turned off.** Even if the service restarts in the middle of a period, nothing new runs on its own. You turn them on yourself in the settings page (หน้าตั้งค่า) when you are testing that period. Every switch on or off is recorded in the log page (หน้าบันทึก) and can be reverted. Database backup has been on since B1.

Runs that did something show up on the page “สิ่งที่เลขาทำ” (what the secretary did). Runs with nothing new (for example, the email watch found no new emails) do not show up, so the page does not get cluttered. The last time each run ran is still visible in the settings page.

## Where the data is stored

| File | What it is |
|---|---|
| `~/.secretary/secretary.db` | v2's central store (kept outside the repo, so it cannot be committed by mistake) |
| `~/.secretary/backups/secretary-YYYY-MM-DD.db` | Daily backup file |
| `~/.secretary/inbox/<โปรเจค>/*.json` | Entry point for other projects (B5). Files that are read are moved to `read/`, and files that cannot be read are moved to `bad/`. The `CONNECT.md` guide is also in this folder |
| `~/.secretary/worktrees/` | Workspace for background work (B5): worktrees for tasks in progress. Deleted automatically when a task finishes. Tasks live on the branch `secretary/<โปรเจค>` in that project and are merged when ready |
| `~/.secretary/ideas-outbox.jsonl` | Ideas captured with Super+I while the secretary was off (B6). The secretary imports them into the library when it starts, then deletes the file. Lines that cannot be read are moved to `.bad` |
| `~/.local/share/activitywatch/` | What ActivityWatch records (B6). It stays on this machine only. The recorder's settings in `~/.config/awatcher/config.toml` are written by the secretary from the block list |
| `backend/.env` | Tokens and secrets (listed in .gitignore) |
| `backend/secretary.db` | v1 data. v2 does not touch this file |

### Restore from a backup

```bash
systemctl --user stop my-secretary
cd ~/.secretary
mkdir -p broken && mv secretary.db* broken/          # keep the current files for now, do not delete
cp backups/secretary-2026-11-05.db secretary.db      # choose the date you want
systemctl --user start my-secretary
```

## Test new code without stopping the running instance

```bash
cd ~/Projects/my_secretary/backend
uv run uvicorn app.main:app --port 8001
```

Then open http://localhost:8001 and press Ctrl+C when you are done.

Things to know:

- You can run it alongside the service, but **the clock and the Discord bot can only run in one instance at a time**.
  - The instance that starts first claims the file `~/.secretary/worker.lock`.
  - The instance that starts later only opens the web page and the API. Its settings page will say “another secretary … is looking after the clock and Discord”.
  - If the first one stops, the remaining one takes over within 30 seconds.
  - This lock stops questions in Discord from getting two answers (this really happened on 5 Nov.), and it stops each run from executing twice.
- The second instance uses the same central store as the real one (`~/.secretary`). If you want to try anything that writes data, point it to a test store **and clear the bot token too**: `SECRETARY_DATA_DIR=/tmp/ลองเลขา SECRETARY_DISCORD_TOKEN= uv run uvicorn app.main:app --port 8001`
  - The lock lives in the store, so a new store cannot see the real instance's lock. The test instance will think it is the first one and start its own clock and bot.
  - If you do not clear the bot token, the second instance connects to Discord with the real token, and every question gets a duplicate answer.
