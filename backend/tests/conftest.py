"""Shared test setup: never touch your real ~/.secretary while testing."""

import os
import tempfile

# Must happen before any app module reads the config.
os.environ["SECRETARY_DATA_DIR"] = tempfile.mkdtemp(prefix="secretary-test-")
os.environ["SECRETARY_TIMEZONE"] = "Asia/Bangkok"
os.environ["SECRETARY_DISCORD_TOKEN"] = ""
