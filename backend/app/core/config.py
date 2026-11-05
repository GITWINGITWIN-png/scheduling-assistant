"""Machine-level configuration, read once from the environment and backend/.env.

Two kinds of "settings" exist in v2, kept apart on purpose:

- **here (config):** secrets and facts about this machine: the Discord token,
  where the data folder is, the time zone. You change them by editing .env and
  restarting.
- **the `settings` table (core/tables.py):** your preferences: which model and
  effort each task uses, the theme, reminder times. The web page changes them
  while the secretary runs.

Every v2 key starts with SECRETARY_. backend/.env still holds v1's keys
(DATABASE_URL pointing at v1's database, an ANTHROPIC_API_KEY, ...), and the
prefix guarantees v2 never picks one of them up by accident.
"""

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]  # .../my_secretary/backend
REPO_DIR = BACKEND_DIR.parent


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SECRETARY_",
        env_file=BACKEND_DIR / ".env",
        extra="ignore",  # v1's keys in the same .env are simply skipped
    )

    # Everything the secretary writes at runtime lives here, outside the repo, so it can't be
    # committed by mistake and survives branch switches: secretary.db, backups/, later inbox/.
    data_dir: Path = Path.home() / ".secretary"
    timezone: str = "Asia/Bangkok"

    # Discord (step 6). Empty = the bot stays off and the rest still runs.
    discord_token: str = ""
    discord_guild_id: int = 0  # your private server
    discord_owner_id: int = 0  # your own user id: the only person the bot listens to

    @property
    def db_path(self) -> Path:
        return self.data_dir / "secretary.db"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_config() -> Config:
    """One Config for the whole process (cached), created on first use."""
    cfg = Config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg
