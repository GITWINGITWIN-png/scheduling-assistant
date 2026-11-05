"""Features: what the secretary actually does.

Each feature owns one job from the plan and combines core (store, Claude,
clock, action log) with the connectors it needs.

Planned, by phase: ask the secretary (B1) · people and mail (B2) ·
schedule and reminders (B3) · morning/evening briefs (B4) · background jobs
and project reading (B5) · ideas and time use (B6) · weekly review (B7).

Rule: features may import core/ and connectors/, never api/. A feature
behaves the same whether the clock, a Discord button or the web page
started it.
"""
