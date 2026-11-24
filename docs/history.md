# History

## v2 (November 2026, tag `v2.0`)

Each phase was planned in chat, built one commit per step on its own branch, checked by the owner, then merged into `v2` with `--no-ff`. The full record of each phase stays in a private build log.

- Planning, 4 and 5 November: the owner's handwritten feature list became [feature.md](../feature.md). A plan board then covered the features (13 features and 12 proposals), the look (a mockup of every screen and 6 themes) and the development plan (phases B1 to B8, the code layout, the data model and the decisions).
- B1, foundation (5 November): the store, the clock and the action log with undo; the Claude caller, with a model and effort per task and tokens recorded; the Discord bot and the web page's shell with themes; the systemd service and the daily backup.
- B2, mail and people (5 November): three tiers with end dates and notes; the 5-minute watch and the 00:00 and 12:00 rounds; appointments into Calendar, tasks from mail and follow-ups; the people page.
- B3, schedule (6 November): planning backwards from deadlines, synced with Google Calendar; Classroom coursework and materials; reminders and the schedule page.
- B4, briefs and today (6 November): the morning and evening briefs, the decisions gathered in one place, and the today page.
- B5, projects and background work (6 November): the project registry, project news and the project inbox; the quota watcher, risk rules, budgets and the stopper; worktrees, #อนุมัติ (approve) and the rules book.
- B6, ideas and time (8 November): the Super+I popup and #ไอเดีย (ideas), with rule tags and groups; ActivityWatch behind the blocklist, categories, and planned against actual time.
- B7, weekly review and questions (8 November): the weekly review with one message per topic and an accept-all button; weekly proposals about people; hours to avoid and focus hours in the planner; nine read-only tools for questions.
- B8, the web page on an iPad: set aside on 8 November; the iPad uses Discord.
- v2 was merged into `main` on 8 November and tagged `v2.0`. Orders (B9) and project news (B10) came after.

## v1 (June to November 2026, tag `v1-final`)

Milestones M0 to M6 were done: the calendar and the chat agent, the dashboard, Google Classroom, the deadline planner, the daily brief, and read-only mail with a local LLM. M7 (mail replies) was not built. M8 (a 3D character companion) is parked and is not part of this repo. The v1 README is in [v1/README.md](v1/README.md).
