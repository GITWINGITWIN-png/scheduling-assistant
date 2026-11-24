# CONNECT.md: send news to the secretary

Other projects can tell the secretary what's new by dropping JSON files into a shared folder. The secretary reads this one way only: it does not reply or edit files in the project, and it does not use a model.

## The easy way: the `secretary-news` command

Run it from inside the project folder (or a subfolder). The command knows which project it belongs to and writes the file in the correct format, as shown below:

```bash
secretary-news report "เสร็จ: feed วันนี้มาแล้ว" --body "12 paper ใหม่" --link https://example.com/feed
secretary-news report "รอเลือกว่าจะใช้ model ไหน" --needs-you
secretary-news schedule "ตรวจผล backtest รอบใหม่" --due 2026-11-12T17:00 --minutes 90
secretary-news status "backtest รอบที่ 14" --state failed --body "หน่วยความจำไม่พอที่ขั้น 3"
```

- Outside the project folder: add `--project <project folder name>`
- Install the command (once, from the secretary's folder): `/usr/bin/python3 desktop/secretary_news.py install`
- Projects that are connected to the secretary (เชื่อมกับเลขา, connected to the secretary) on the project page (หน้าโปรเจค, project page) have a note in `CLAUDE.local.md` telling Claude, when working in that project, to use this command itself.
- The secretary reads the inbox every 5 minutes, once the round อ่านข่าวจากโปรเจค (read news from projects) is turned on in the หน้าตั้งค่า (settings page).

## Placing the file yourself: where

```
~/.secretary/inbox/<ชื่อโฟลเดอร์โปรเจคใน ~/Projects>/<ชื่ออะไรก็ได้>.json
```

The folder name must match the project's folder in `~/Projects` (for example `research_labs`). The secretary links the news to that project.

One file = one topic. After reading, the secretary moves the file into `read/` inside that folder. Files it cannot read are moved to `bad/`, and it reports this in the news.

Write the file completely first, then move (or rename) it into the folder. That way the secretary won't read a file that is still being written. Files whose names start with `.` are skipped.

## Three types

**report**: news that something is new (a feed run's results or an experiment summary)

```json
{"kind": "report", "title": "feed วันนี้มาแล้ว: Diffusion for time series", "body": "12 paper ใหม่", "link": "https://example.com/feed/2026-11-06"}
```

**schedule**: a plan that becomes a task on the secretary's schedule, with a due date and the time it needs

```json
{"kind": "schedule", "title": "ตรวจผล backtest รอบใหม่", "due": "2026-11-12T17:00:00+07:00", "minutes": 90}
```

**status**: the status of a project's automatically running job

```json
{"kind": "status", "title": "backtest รอบที่ 14", "status": "failed", "body": "หน่วยความจำไม่พอที่ขั้น 3"}
```

## Fields that work in every type

| Field | Required? | Description |
|---|---|---|
| `kind` | Required | `report`, `schedule`, `status` |
| `title` | Required | Short one-line headline |
| `body` | Optional | Details |
| `link` | Optional | Link for more information |
| `at` | Optional | When it happened (ISO 8601). If left out, it is the time the secretary reads the file |
| `failed` | Optional | `true` if the job failed (`status: "failed"` also counts) |
| `needs_you` | Optional | `true` if the owner needs to make a decision |
| `due`, `minutes` | schedule | Due date (ISO 8601) and time needed (minutes) |
| `status` | status | `running`, `done`, `failed`, `paused` |

## When to alert immediately

News marked `failed` or `needs_you` from a project with potential S to A, or urgency 4 to 5, is posted to #ด่วน (urgent) on Discord right away.

Other news is combined into the morning summary (สรุปเช้า) at 07:00, and appears on the project page and the หน้าวันนี้ (Today page).
