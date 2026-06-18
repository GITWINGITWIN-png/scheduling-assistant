"""Google Calendar access.

This is the M0 milestone: prove we can authenticate to Google and read/write
events. Everything else (the chat agent, the planner) eventually calls these
two methods, so we keep the Google-specific details isolated here.

Auth model: we use the OAuth "installed app" flow. On first run it opens a
browser for you to grant access, then caches a token so future runs are silent.
When we move to the full web app (M2) we'll switch to the web OAuth flow, but
this is the simplest thing that works for local development.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import settings

# Full read/write access to calendars. Narrow this later if you only need reads.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_credentials() -> Credentials:
    """Load cached credentials, refresh them, or run the consent flow once."""
    creds: Credentials | None = None

    if os.path.exists(settings.google_token_file):
        creds = Credentials.from_authorized_user_file(settings.google_token_file, SCOPES)

    # If there are no (valid) credentials, refresh or ask the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(settings.google_credentials_file):
                raise FileNotFoundError(
                    f"Missing {settings.google_credentials_file}. Download your OAuth "
                    "client file from Google Cloud Console (see README)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.google_credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Cache for next time.
        with open(settings.google_token_file, "w") as token:
            token.write(creds.to_json())

    return creds


def _service():
    """Build a Google Calendar API client."""
    return build("calendar", "v3", credentials=_get_credentials())


def _rfc3339(dt: datetime) -> str:
    """Format a datetime as RFC 3339 for the Google API.

    Naive datetimes are assumed to be UTC. Aware datetimes keep their offset.
    (Avoids the old `isoformat() + "Z"` trick, which breaks on aware datetimes.)
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def list_events(time_min: datetime, time_max: datetime, max_results: int = 50) -> list[dict]:
    """Return events between two datetimes, soonest first."""
    result = (
        _service()
        .events()
        .list(
            calendarId=settings.calendar_id,
            timeMin=_rfc3339(time_min),
            timeMax=_rfc3339(time_max),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def create_event(
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
) -> dict:
    """Create a timed event and return the created resource."""
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    return (
        _service()
        .events()
        .insert(calendarId=settings.calendar_id, body=body)
        .execute()
    )
