"""Google accounts: the sign-in that Gmail, Calendar and (B3) Classroom calls use.

Accounts and what each may do are in ACCOUNTS:

- gmail (หลัก, your everyday Gmail): read Gmail, read and write Calendar. Appointments
  and work blocks from every account go into its calendars (CALENDAR_ACCOUNT), so you have
  one schedule.
- ku (KU, the @ku.th address; v1's token.json, which v1 called "personal"): read Gmail,
  and since B3 also Classroom (CLASSROOM_ACCOUNT): courses, coursework and materials, plus
  read-only Drive to download the materials' files. Its old token also allows Calendar;
  that grant is kept but not used. (v1 had a separate token for Classroom on the same
  @ku.th address; B3 merged it here, the user confirmed it is one account.)

Each feature asks only for the permissions it uses (`credentials(account, *need)`), so
KU's mail watch keeps working while the Classroom permissions are not granted yet.
No address is written here: an account is whoever signs in during `connect`, and the
settings page shows the address the watch found.

Every account uses the same OAuth client (backend/credentials.json, v1's, outside git).
Each account keeps its own token in ~/.secretary/google/<account>.json (mode 0600, outside
the repo). The token holds a refresh token, so after one consent, calls stay signed in.

Connecting an account (once; it opens your browser):

    cd backend && uv run python -m app.connectors.google connect ku
    cd backend && uv run python -m app.connectors.google status

v1's token (backend/token.json) is copied on first use. An account
whose old token already allows everything listed here never has to consent again.

Why the token is loaded with the scopes it was *granted* (not just the ones a caller
needs): a refresh writes the token back, and writing back a subset would silently drop
permissions. v1 had exactly that bug (fixed in 56f6a96).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# Google sometimes grants a substitute for a requested Classroom scope (see SUBSTITUTES).
# By default oauthlib then refuses the whole consent, so relax that check; status() still
# verifies that every needed permission is covered.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google.auth.exceptions import RefreshError  # noqa: E402
from google.auth.transport.requests import Request  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402

from app.core.config import BACKEND_DIR, get_config  # noqa: E402

GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR = "https://www.googleapis.com/auth/calendar"
CLASSROOM = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
]
CLASSROOM_MATERIALS = "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly"
DRIVE_READ = "https://www.googleapis.com/auth/drive.readonly"  # to download a material's file
CLASSROOM_ALL = (*CLASSROOM, CLASSROOM_MATERIALS)
# Google hands back student-submissions.me.readonly when asked for coursework.me.readonly
SUBSTITUTES = {CLASSROOM[1]: {CLASSROOM[1], "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly"}}


@dataclass(frozen=True)
class Account:
    id: str
    label: str
    scopes: tuple[str, ...]
    does: str  # what the secretary uses it for, in your words (settings page)
    v1_token: str | None = None  # file name in backend/ that v1 used for this account, if any


ACCOUNTS = {
    "gmail": Account("gmail", "หลัก", (GMAIL_READ, CALENDAR), "Gmail อ่านอย่างเดียว · ปฏิทิน อ่านและเขียน (นัดและบล็อกงานลงที่นี่)"),
    "ku": Account("ku", "KU", (GMAIL_READ, *CLASSROOM_ALL, DRIVE_READ),
                  "Gmail อ่านอย่างเดียว · Classroom และไฟล์สื่อการเรียน อ่านอย่างเดียว", "token.json"),
}
CALENDAR_ACCOUNT = "gmail"  # where appointments and work blocks are written
CLASSROOM_ACCOUNT = "ku"


class NeedsConsent(Exception):
    """The account isn't connected, or its token lacks a permission. The message says what to run."""

    def __init__(self, account: str, why: str) -> None:
        super().__init__(f"บัญชี {ACCOUNTS[account].label}: {why} · รัน "
                         f"`cd backend && uv run python -m app.connectors.google connect {account}`")
        self.account = account


def token_path(account: str) -> Path:
    return get_config().google_dir / f"{account}.json"


def granted(account: str) -> set[str]:
    """The permissions recorded in the account's token file (what Google actually granted)."""
    try:
        return set(json.loads(token_path(account).read_text()).get("scopes") or [])
    except (OSError, json.JSONDecodeError):
        return set()


def missing(account: str, need: tuple[str, ...] = ()) -> list[str]:
    """Which of `need` (default: everything the account asks for) the token doesn't allow."""
    have = granted(account)
    return [s for s in (need or ACCOUNTS[account].scopes) if not (SUBSTITUTES.get(s, {s}) & have)]


def _save(account: str, creds: Credentials) -> None:
    path = token_path(account)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(creds.to_json())
    tmp.chmod(0o600)  # it holds a refresh token: as good as a password for these permissions
    tmp.replace(path)


def import_v1(account: str) -> bool:
    """Copy v1's token for this account once, if v2 has none yet. Returns True if copied."""
    if ACCOUNTS[account].v1_token is None:
        return False
    old, new = BACKEND_DIR / ACCOUNTS[account].v1_token, token_path(account)
    if new.exists() or not old.exists():
        return False
    new.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copyfile(old, new)
    new.chmod(0o600)
    return True


def credentials(account: str, *need: str) -> Credentials:
    """Signed-in credentials for one account, refreshed if expired. Raises NeedsConsent.

    need: the permissions this caller uses (default: all of the account's). Only those
    are checked, so a feature still works while another one waits for consent."""
    import_v1(account)
    if not token_path(account).exists():
        raise NeedsConsent(account, "ยังไม่ได้เชื่อม")
    if lacking := missing(account, need):
        raise NeedsConsent(account, f"ยังไม่ได้อนุญาต {', '.join(s.rsplit('/', 1)[-1] for s in lacking)}")
    creds = Credentials.from_authorized_user_file(str(token_path(account)), sorted(granted(account)))
    if not creds.valid:
        try:
            creds.refresh(Request())
        except RefreshError as exc:  # revoked, or a password change on the account
            raise NeedsConsent(account, f"การอนุญาตหมดอายุหรือถูกยกเลิก ({exc})") from exc
        _save(account, creds)
    return creds


def connect(account: str) -> None:
    """Run the consent in your browser and save the token (asks for everything the account needs)."""
    from google_auth_oauthlib.flow import InstalledAppFlow  # only needed here

    client = get_config().google_client_file
    if not client.exists():
        raise SystemExit(f"ไม่พบ {client} (OAuth client ของ v1) · ดาวน์โหลดจาก Google Cloud Console")
    import_v1(account)
    scopes = sorted(set(ACCOUNTS[account].scopes) | granted(account))  # never lose an earlier grant
    flow = InstalledAppFlow.from_client_secrets_file(str(client), scopes)
    print(f"\nเบราว์เซอร์จะเปิดขึ้น · ล็อกอินด้วยบัญชี {ACCOUNTS[account].label} แล้วกดอนุญาต\n")
    creds = flow.run_local_server(port=0, prompt="consent")  # "consent" so Google returns a refresh token
    _save(account, creds)


FEATURE_NAMES = {GMAIL_READ: "Gmail", CALENDAR: "ปฏิทิน", **{s: "Classroom" for s in CLASSROOM_ALL}, DRIVE_READ: "ไฟล์ใน Drive"}


def _features(scopes) -> list[str]:
    return list(dict.fromkeys(FEATURE_NAMES.get(s, s.rsplit("/", 1)[-1]) for s in scopes))


def status() -> list[dict]:
    """For the settings page. Reads the token files only (no network), so it's cheap to poll."""
    out = []
    for acc in ACCOUNTS.values():
        import_v1(acc.id)
        connected = token_path(acc.id).exists()
        lacking = missing(acc.id) if connected else list(acc.scopes)
        if not connected:
            why = "ยังไม่ได้เชื่อม"
        elif lacking:  # say what already works, so "missing Classroom" doesn't read as "mail is broken"
            works = [f for f in _features(acc.scopes) if f not in _features(lacking)]
            why = (f"{' · '.join(works)} ใช้ได้ · " if works else "") + f"ยังไม่ได้อนุญาต {' · '.join(_features(lacking))}"
        out.append({
            "id": acc.id, "label": acc.label, "does": acc.does, "connected": connected and not lacking,
            "problem": "" if connected and not lacking else str(NeedsConsent(acc.id, why)),
        })
    return out


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["connect", account] if account in ACCOUNTS:
            connect(account)
            print("เชื่อมแล้ว" if not missing(account) else f"ยังขาด: {missing(account)}")
        case ["status"]:
            for row in status():
                print(f"{row['label']:12} {'เชื่อมแล้ว' if row['connected'] else row['problem']}")
        case _:
            raise SystemExit(f"ใช้: python -m app.connectors.google connect {{{'|'.join(ACCOUNTS)}}} | status")
