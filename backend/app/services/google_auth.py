"""Account-scoped Google OAuth.

M0 used a single hardcoded token file for one Google account. M3 introduces a
second account (the *school* account that owns Google Classroom), so we
generalize credential loading here:

    get_credentials(account, scopes)

`account` is a short label ("personal", "school"). Each account caches its own
token file so the two logins never collide:

    personal -> token.json          (kept as-is for back-compat with M0)
    school   -> token_school.json
    <other>  -> token_<other>.json

All accounts share the *same* OAuth client (credentials.json) — Google lets one
desktop client be authorized by multiple accounts. We use the "installed app"
flow: first use opens a browser to grant access, then the token is cached so
later runs are silent.
"""

from __future__ import annotations

import json
import os

# Google is migrating some Classroom scopes (e.g. it hands back
# `classroom.student-submissions.me.readonly` when you ask for
# `classroom.coursework.me.readonly`). By default oauthlib raises on ANY such
# difference between requested and granted scopes. Relaxing this lets the flow
# accept Google's substituted/superset scopes; we still verify access by
# actually calling the API (and surface ACCESS_TOKEN_SCOPE_INSUFFICIENT loudly).
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google.auth.transport.requests import Request  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402
from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from app.config import settings  # noqa: E402


def _token_path(account: str) -> str:
    """Where a given account's cached token lives."""
    if account == "personal":
        # Back-compat: M0 already wrote token.json for the personal account.
        return settings.google_token_file
    return f"token_{account}.json"


# Google may grant a different scope than the one requested. Map each requested
# scope to the set of grants that should count as satisfying it, so the
# "do we need to re-consent?" check below doesn't loop forever on a substitution.
_COURSEWORK_ME_RO = "https://www.googleapis.com/auth/classroom.coursework.me.readonly"
_SUBMISSIONS_ME_RO = "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly"
_SCOPE_SUBSTITUTIONS: dict[str, set[str]] = {
    _COURSEWORK_ME_RO: {_COURSEWORK_ME_RO, _SUBMISSIONS_ME_RO},
}


def _scope_satisfied(requested: str, granted: set[str]) -> bool:
    """True if `granted` contains the requested scope or an accepted substitute."""
    return bool(_SCOPE_SUBSTITUTIONS.get(requested, {requested}) & granted)


def _granted_scopes(token_file: str) -> set[str]:
    """The scopes Google actually granted, as recorded in the token file.

    We read the file's own "scopes" field rather than `creds.scopes`, because
    `Credentials.from_authorized_user_file(file, scopes)` sets `creds.scopes` to
    the scopes we *request*, not the ones that were *granted* — so it can't tell
    us whether a saved token is missing a newly-added scope.
    """
    try:
        with open(token_file) as f:
            return set(json.load(f).get("scopes") or [])
    except (OSError, json.JSONDecodeError):
        return set()


def get_credentials(account: str, scopes: list[str]) -> Credentials:
    """Load cached credentials for `account`, refresh them, or run consent once.

    If the cached token was granted *fewer* scopes than `scopes` asks for (e.g.
    we widened a feature's access), we discard it and re-run consent so Google
    can grant the new scopes — otherwise the API would 403 on the new calls.
    """
    token_file = _token_path(account)
    creds: Credentials | None = None
    granted = _granted_scopes(token_file)

    if os.path.exists(token_file):
        # Load with the UNION of what this caller needs and what the file already
        # records as granted. `creds.scopes` becomes that union, so when a refresh
        # re-writes the token (creds.to_json()), it persists the full grant rather
        # than shrinking it to this caller's subset. Without this, e.g. the
        # calendar service (which requests only `calendar`) would, on refresh, drop
        # `gmail.readonly` from the shared token.json — forcing Gmail to re-consent,
        # which then drops calendar's view, and so on: a browser prompt every hour.
        creds = Credentials.from_authorized_user_file(
            token_file, sorted(set(scopes) | granted)
        )

    # Drop the token if Google's *granted* scopes don't cover what we need now
    # (accepting Google's known scope substitutions, so we don't re-consent in a
    # loop). A genuinely new scope we've never been granted still triggers consent.
    if creds:
        if not all(_scope_satisfied(s, granted) for s in scopes):
            creds = None

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
                settings.google_credentials_file, scopes
            )
            print(
                f"\n>>> A browser will open. Authorize the {account.upper()} "
                "Google account. <<<\n"
            )
            creds = flow.run_local_server(port=0)
        # Cache for next time.
        with open(token_file, "w") as token:
            token.write(creds.to_json())

    return creds
