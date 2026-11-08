"""API: the web pages' door into the secretary.

FastAPI routers, one per page area: ask, log and settings in B1, then
people, schedule, today, jobs, ideas, time, rules and decisions with their
phases. A route only checks the input, calls a feature and shapes the reply.
The logic stays in features/, so Discord and the web page behave the same.

Rule: api may import features/ and core/. Nothing imports api except
main.py.
"""
