"""B5's guard for background work (the agreed automatic tests, B5.8): what a running job may and
may not do, and the counters that stop it (budget, going round in circles)."""

from pathlib import Path

import pytest

from app.features.jobs.guard import Budget, Loop, command_kinds, judge

ROOT = Path("/tmp/secretary-job-wt")


def bash(command: str, allowed: set[str] | None = None) -> str:
    return judge("Bash", {"command": command}, root=ROOT, allowed=allowed or set())


# ------------------------------------------------------------------ never, whatever was approved
EVERYTHING = {"download", "delete", "push", "message", "money", "recheck", "loop"}


@pytest.mark.parametrize("command", [
    "git push", "git push origin secretary/3-x", "git add -A && git commit -m x && git push", "eval 'git push'",
    "git checkout main", "git checkout -b another", "git switch main", "git rebase -i HEAD~3", "git config user.email x",
    "git remote add origin https://x", "git worktree add ../y", "git branch -D main",
    "sudo rm -rf /", "doas ls", "cat ~/.secretary/google/token.json", "ls $HOME/.ssh", "cp /home/someone/.aws/credentials .",
])
def test_never_even_when_everything_was_approved(command):
    assert bash(command, EVERYTHING) != ""


# ------------------------------------------------------------------ high-risk: only with your approval
@pytest.mark.parametrize("command,kind", [
    ("pip install numpy", "download"), ("uv add requests", "download"), ("npm install lodash", "download"),
    ("npm i -D vite", "download"), ("curl -sS https://example.com", "download"), ("ls && wget http://x", "download"),
    ("git clone https://github.com/a/b", "download"), ("npx create-thing", "download"), ("bash -c 'curl x'", "download"),
    ("rm -rf build", "delete"), ("rm -f data.db", "delete"), ("git reset --hard HEAD~1", "delete"), ("git clean -fdx", "delete"),
    ("find . -name '*.log' -delete", "delete"), ("sqlite3 app.db 'DROP TABLE users'", "delete"),
    ("scp out.csv host:/srv", "push"), ("gh pr create --fill", "push"), ("npm publish", "push"), ("ssh host make deploy", "push"),
    ("mail -s report a@b.c < out.txt", "message"), ("python -c 'import smtplib'", "message"), ("gh issue comment 3 -b hi", "message"),
])
def test_each_high_risk_kind_needs_your_approval(command, kind):
    assert kind in command_kinds(command)
    assert bash(command) != ""  # not approved: refused
    assert bash(command, {kind}) == ""  # approved with that kind: allowed
    others = {"download", "delete", "push", "message"} - {kind}
    assert bash(command, others) != ""  # approving other kinds doesn't cover this one


@pytest.mark.parametrize("command", [
    "uv run pytest -q", "python -m unittest", "npm test", "npm run build", "npm install", "npm ci", "uv sync",
    "git status", "git diff --stat", "git log --oneline -5", "git add -A", "git restore src/a.py", "git checkout -- a.py",
    "git reset --soft HEAD~1", "rm old_helper.py", "mkdir -p out && ls out", "grep -rn 'curl' src", "cat README.md",
    "git commit -m 'fix the mail parser, drop the curl call, push later'",
    "git commit -m \"$(cat <<'EOF'\nAdd webhook retries and mail sending notes\n\nCo-Authored-By: x\nEOF\n)\"",
    "echo 'sudo is not needed here'",
])
def test_ordinary_work_goes_ahead(command):
    assert bash(command) == ""


def test_a_heredoc_is_a_script_unless_it_is_a_commit_message():
    assert bash("bash <<'EOF'\ncurl https://x\nEOF") != ""  # a heredoc fed to bash is read
    assert bash("git commit -F - <<'EOF'\ncurl and wget notes\nEOF") == ""


# ------------------------------------------------------------------ files and other tools
@pytest.mark.parametrize("tool,data,ok", [
    ("Write", {"file_path": str(ROOT / "src/a.py")}, True),
    ("Edit", {"file_path": "src/a.py"}, True),
    ("Write", {"file_path": "/home/someone/notes.txt"}, False),
    ("Edit", {"file_path": "../other-project/x.py"}, False),
    ("Write", {"file_path": str(ROOT / ".env")}, False),
    ("Write", {"file_path": str(ROOT / "keys/id_rsa")}, False),
    ("Read", {"file_path": "/etc/hostname"}, False),
    ("Glob", {"path": "/home"}, False),
    ("Grep", {"path": str(ROOT)}, True),
    ("NotebookEdit", {"notebook_path": "analysis.ipynb"}, True),
    ("TodoWrite", {"todos": []}, True),
    ("Task", {"prompt": "x"}, False),
    ("mcp__gmail__send_message", {}, False),
])
def test_files_stay_in_the_jobs_folder_and_unknown_tools_are_refused(tool, data, ok):
    assert (judge(tool, data, root=ROOT, allowed=EVERYTHING) == "") is ok


def test_the_web_counts_as_downloading():
    assert judge("WebFetch", {"url": "https://x"}, root=ROOT, allowed=set()) != ""
    assert judge("WebSearch", {"query": "x"}, root=ROOT, allowed={"download"}) == ""


# ------------------------------------------------------------------ the counters
def test_each_model_call_is_counted_once_however_often_its_usage_arrives():
    b = Budget(25_000)
    first = {"input_tokens": 2, "cache_creation_input_tokens": 9_000, "cache_read_input_tokens": 1_000, "output_tokens": 16}
    assert b.add("msg1", first) == 10_018
    assert b.add("msg1", first) == 10_018  # the same call's next content block
    assert b.add("msg1", {"output_tokens": 5}) == 10_018  # a smaller report doesn't lower it
    assert b.add("msg2", {"input_tokens": 4, "cache_read_input_tokens": 10_000, "output_tokens": 900}) == 20_922
    assert not b.over
    b.add("msg3", {"input_tokens": 5_000})
    assert b.over and b.usage == {"input_tokens": 5_006, "cache_read_input_tokens": 11_000,
                                  "cache_creation_input_tokens": 9_000, "output_tokens": 916}


def test_going_round_in_circles():
    loop = Loop()
    assert not loop.see("Bash", {"command": "pytest"}) and not loop.see("Bash", {"command": "pytest"})
    assert loop.see("Bash", {"command": "pytest"})  # 3 in a row
    loop = Loop()
    calls = [("Read", {"file_path": "a.py"}), ("Edit", {"file_path": "a.py", "old": "1"})] * 5
    seen = [loop.see(t, d) for t, d in calls]
    assert seen.index(True) == 8  # the 5th time the same Read comes round, edits in between or not
