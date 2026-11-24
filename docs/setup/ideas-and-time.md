# Noting ideas and logging time use (B6)

These two run on your screen, not in the secretary's service:

- **The Super+I shortcut** opens the idea-note window.
- **ActivityWatch** records which apps and windows you use.

Both talk to the secretary only through `localhost`.

## Super+I: จดไอเดีย (note an idea)

Press Super+I from any screen. A small window (K1) opens:

- Type the idea and press **Enter** to save it.
- **Shift+Enter** starts a new line.
- **Esc** closes without saving.

While you type, the secretary suggests tags using rules (no model is used). Tags come from 3 sources:

1. Hashtags you type yourself
2. Names of projects you mention
3. Tags you have used before

Suggested tags are already selected. Click one to remove it, or press **+ แท็ก (+ tag)** to add your own.

After saving, the window says which group the idea will go into, then closes by itself. The idea ends up in the same place as what you type in #ไอเดีย (#ideas channel) on Discord and in the note box (ช่องจด) on the หน้าไอเดีย (Ideas page).

If the secretary is not running (or is still a version before B6), ideas are not lost:

- The window saves them in `~/.secretary/ideas-outbox.jsonl`.
- The secretary imports them into the store the next time it starts.

| Want to | Command |
|---|---|
| Bind Super+I (I already bound it for you during B6) | `/usr/bin/python3 desktop/idea_key.py on` |
| Remove it | `/usr/bin/python3 desktop/idea_key.py off` |
| See what is bound | `/usr/bin/python3 desktop/idea_key.py` |
| Try opening the window yourself | `/usr/bin/python3 desktop/idea_popup.py` |

- This shortcut is one of GNOME's "Custom Shortcut" entries. You can see and edit it under **Settings → Keyboard → Custom Shortcuts**, named "จดไอเดีย (เลขา)".
- `off` removes only this one. Your other shortcuts are not touched.
- `on` refuses to run if Super+I is already used for something else.
- The window uses the system Python (`/usr/bin/python3`) because GTK 4 comes with Ubuntu and is not in the backend's venv.
- If you move the repo folder, run `on` again.

## ActivityWatch: บันทึกการใช้เวลา (log time use)

It uses awatcher v0.4.0 as a single "bundle" file that contains both the ActivityWatch server and web page (http://localhost:5600) and the window recorder:

- **Why awatcher:** on GNOME + Wayland, ActivityWatch's own window watcher cannot see windows.
- **Why an extension is needed:** GNOME does not tell other programs which window is in front, so awatcher needs the GNOME **Focused Window D-Bus** extension. This extension does only one thing: it answers with the window's name over D-Bus (I read its code before installing it).
- **Not AppImage or Flatpak:** those two cannot see windows on Wayland.

### Installation (I installed it for you during B6, without sudo)

```bash
/usr/bin/python3 desktop/activitywatch.py install    # ดาวน์โหลด ตรวจ SHA-256 แล้วติดตั้ง
/usr/bin/python3 desktop/activitywatch.py            # ดูว่าติดตั้งอะไรไว้
/usr/bin/python3 desktop/activitywatch.py uninstall  # เอาออกทั้งหมด
```

| What is installed | Where |
|---|---|
| awatcher | `~/.local/bin/awatcher` |
| GNOME extension | `~/.local/share/gnome-shell/extensions/focused-window-dbus@flexagoon.com` (enabled at your next login) |
| systemd user unit | `~/.config/systemd/user/awatcher.service` (**not enabled**) |
| awatcher settings | `~/.config/awatcher/config.toml` (the secretary writes this from your do-not-record list, so you don't need to edit it yourself) |
| Where ActivityWatch stores data | `~/.local/share/activitywatch/` (stays on this machine only; it remains after uninstalling, and you can delete it yourself) |

After installing, you must **log out and log back in once**, because GNOME on Wayland can only load extensions at login.

### Turning it on and off

Everything is on the **หน้าการใช้เวลา (Time usage page)**, in the "ความเป็นส่วนตัว" (Privacy) card:

- **The "บันทึกกิจกรรม" (Record activity) switch**
  - On: the secretary first writes awatcher's settings from the do-not-record list, then runs `systemctl --user enable --now awatcher`, and turns on the read cycle every 15 minutes.
  - Off: both stop, and nothing starts automatically at login.
- **"หยุดบันทึก 1 ชั่วโมง" (Pause recording for 1 hour)** (or 15 minutes or 3 hours)
  - It stops the recorder immediately, then systemd's one-time timer turns it back on automatically when the time is up, even if the secretary is not running.
  - The paused period is also logged. Anything recorded during that period, the secretary will not keep.
  - "บันทึกต่อเลย" (Resume now) ends the pause before the time is up.
- **"ห้ามบันทึก … แก้" (Do not record … Edit)** has 3 types:
  - **แอป (Apps):** never recorded
  - **เว็บและชื่อหน้าต่าง (Websites and window titles):** never recorded
  - **คำในชื่อหน้าต่าง (Words in window titles):** the time is kept, but the window title is hidden

  After you add a rule, the secretary also deletes existing matching entries from the log, then restarts awatcher so it uses the new rule.

The filter works in 2 layers:

1. **In awatcher:** blocked windows are never sent to ActivityWatch.
2. **When the secretary reads:** it filters again before storing.

| Want to know | Command |
|---|---|
| Is the recorder running | `systemctl --user status awatcher` |
| The recorder's log | `journalctl --user -u awatcher -n 50` |
| Is the GNOME extension working | `gnome-extensions info focused-window-dbus@flexagoon.com` should show `State: ACTIVE` |

## Comparing the plan with what was actually done

Each time the secretary reads ActivityWatch (every 15 minutes), a finished work block in the schedule gets one of these results:

| Result | When | What the schedule does next |
|---|---|---|
| ทำแล้ว (Done) | You worked on that block for at least half of it | Counted as done (green, with the actual time spent) |
| หลุดแผน (Off plan) | You were at the computer for at least half the block, but doing something else | Only the minutes you actually spent on that work are counted. The rest goes back to the task, and the scheduler (ตัววางตาราง) finds a new time for it |
| ไม่ได้ใช้คอม (Not using the computer) | You were not at the computer for more than half the block | Counted as done (you may have worked away from the computer, such as reading a book) |
| ไม่มีข้อมูล (No data) | The recorder was not running for more than half the block (off, or paused) | Counted as done, no judgment made |

What counts as "working on that block" is decided by these rules:

- Project work (time bookings, ideas turned into tasks, project news): the time spent in that project
- Work from Classroom: the time you labeled "เรียน" (Study)
- Work from email: the time spent in email
- All kinds of work: windows whose title contains a word from the task name (English words of 3 or more letters that stand as separate words, Thai words of 3 or more characters)

If the secretary says you went off plan, but you actually worked away from the computer, click the block on the schedule page, then press **"นับว่าทำแล้ว (ทำนอกคอม)" (Count as done (off computer))**.

You can see the results at:

- **The หน้าตาราง (Schedule page):**
  - the block colors
  - the card "ทำตามแผนได้ X%" (Followed the plan X%), compared with the target (click the target to change it, default 80%)
  - an "ข้อสังเกต" (Observations) note when the same time slot slips off plan 2 or more weeks in a row
- **หน้าวันนี้ (Today page):** the "ทำจริง" (Actual) row
- **ทบทวนเย็น 21:00 (Evening review at 21:00):**
  - "ทำตามตารางได้ X จาก Y บล็อก" (Followed the schedule for X of Y blocks)
  - Blocks that slipped, what you did instead, and where the secretary moved the time to
  - the "ย้าย … ไปพรุ่งนี้" (Move … to tomorrow) button, when the new time is tonight
