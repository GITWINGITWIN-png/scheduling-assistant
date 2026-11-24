# Features

The secretary speaks Thai, so its channels, pages and buttons have Thai names. Each Thai name below is followed by its meaning.

## Where you reach it

A private Discord server works the same from the computer, a tablet or a phone. The bot creates five channels:

- #คุยกับเลขา (talk to the secretary): questions and orders.
- #ด่วน (urgent): mail from important people, appointments it added to the calendar, and reminders before appointments and deadlines.
- #สรุป (summaries): the morning brief, the evening review and the weekly review.
- #อนุมัติ (approve): plans that need a yes, with buttons.
- #ไอเดีย (ideas): ideas typed from any device.

The web page at http://localhost:8000 has pages for today, people and mail, projects, background work, the schedule, ideas, time use, the rules book, what the secretary did, and settings. The top bar holds the ask box, a bell that lists everything waiting for you, a theme picker with 6 themes, and a button to jot an idea.

## Mail and people

Every email is checked, read or not, in a big round at 00:00 and a small one at 12:00. Important people and keywords are watched every 5 minutes.

Senders sit in one of three tiers:

- สำคัญ (important): you are told at once. Each person has an end date and a note about why they are important.
- สนใจ (interested): one summary per person per day. First-time senders start here.
- ไม่สนใจ (ignored): subjects only.

Appointments from important people go straight into Google Calendar, with a link to the email and an undo. Appointments from interested people wait for your yes. Tasks found in mail, and replies you are waiting for, are tracked until they close. Gmail access is read-only.

## Schedule

One week combines Google Calendar, Classroom coursework, tasks from mail, projects and your own tasks. Work blocks are planned backwards from deadlines and synced to Google Calendar. They respect your rules: hours to avoid, and focus hours that are filled first. Reminders go out before appointments and deadlines, and each block is compared with what you actually did, using ActivityWatch.

## Briefs and reviews

The morning brief at 07:00 lists important mail, who sent what, today's appointments, project news and what is waiting for you. The evening review at 21:00 compares the day with the plan.

The weekly review on Sunday at 19:00 sends one message per topic: people to renew or move, the schedule, time use, projects that have gone quiet, and idea groups that have grown. Each topic says why, what it will do, how, and how far, and one button accepts every default.

## Projects and background work

The secretary scans `~/Projects` and reads each project's `PROGRESS.md`. The button เชื่อมทุกโปรเจค (connect every project) on the projects page writes a note into each project's `CLAUDE.local.md`, a file git ignores; the project's own `CLAUDE.md` is left alone. The note asks Claude Code working in that project to report finished steps, questions, deadlines and automatic runs with the `secretary-news` command, which scripts can call too. The news shows on the today and projects pages and in the morning brief. The format is in [CONNECT.md](CONNECT.md).

When work in a project stops, because the quota ran out or you were interrupted, the secretary plans how to continue. Each plan has a risk score, a model and effort, and a token budget. Low-risk plans run on their own while more than 70% of the week's quota is left, and everything else asks in #อนุมัติ. The work happens in a git worktree on its own branch, and stops when it goes over budget or starts repeating itself.

## Ideas and time use

You jot an idea with Super+I on the computer, or in #ไอเดีย from any device. Ideas are tagged by rules and grouped twice a day, and a group that grows can become a project or a task.

ActivityWatch records which window is in front. A privacy blocklist is applied twice: before anything is stored, and again when the secretary reads it. Time is sorted into categories and projects by rules. Recording stays off until you switch it on.

## Questions and orders

You ask in #คุยกับเลขา or in the ask box on the web page. Sonnet answers quickly from read-only tools over every part of the store, with links to the sources. The tools cover people and mail, replies you are waiting for, the schedule, tasks and projects, ideas, time use, Classroom and the rules book. The button ให้ Opus คิดต่อ (let Opus think further) hands a question on to Opus.

An order goes to Opus and does at most 25 things, because a Discord message holds at most 25 buttons. The chat remembers the conversation, so ทำต่อ (carry on) continues it. The action tools cover tasks and appointments, keeping hours free, replanning, people's tiers, follow-ups, ideas, rules written as a sentence, continuing a project, and answering what is waiting for you.

Each tool calls the same function a page button calls, so the action is logged with its undo. The answer lists what was done, with ย้อนกลับ (undo) for each item. Anything that cannot be undone waits for ทำเลย (do it now). A request that needs planning gets a plan instead; when you approve it, the secretary carries it out, and the steps only you can do become tasks. An order never sends anything, deletes anything or changes settings.
