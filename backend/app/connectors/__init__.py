"""Connectors: reach outside systems, and nothing more.

One module per outside system. A connector knows *how* to reach it (auth,
API calls, retries), not *why*: deciding what an email means is a feature's
job, not the Gmail connector's. That keeps a system swappable without
touching the features that use it.

Planned, by phase: Discord bot (B1) · Google auth + Gmail read-only (B2) ·
Calendar + Classroom (B3) · project inbox + project runner (B5) ·
ActivityWatch + OmniRoute (B6) · Tailscale-only access (B8).

Rule: connectors may import core/ (settings, the action log), never
features/ or api/.
"""
