"""The restart banner's check: is the backend code on disk different from the running code?"""

import os

from app.core import codestamp


def _point_at(monkeypatch, root):
    """Make the module look at a small fake backend/ and start from what's there now."""
    monkeypatch.setattr(codestamp, "ROOT", root)
    started = codestamp._content()
    monkeypatch.setattr(codestamp, "STARTED", started)
    monkeypatch.setattr(codestamp, "_last", (codestamp._signature(), started))


def test_a_changed_file_means_the_running_code_is_old(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    code = tmp_path / "app" / "tasks.py"
    code.write_text("A = 1\n")
    _point_at(monkeypatch, tmp_path)
    assert not codestamp.stale()
    code.write_text("A = 2\n")
    assert codestamp.stale()
    code.write_text("A = 1\n")  # changed back: the running code matches again
    assert not codestamp.stale()


def test_touching_a_file_without_changing_it_is_not_a_change(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    code = tmp_path / "app" / "tasks.py"
    code.write_text("A = 1\n")
    _point_at(monkeypatch, tmp_path)
    os.utime(code, ns=(1, 1))
    assert not codestamp.stale()


def test_a_new_migration_counts_too(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    (tmp_path / "migrations" / "versions").mkdir(parents=True)
    _point_at(monkeypatch, tmp_path)
    (tmp_path / "migrations" / "versions" / "2026_11_06-abc_details.py").write_text("revision = 'abc'\n")
    assert codestamp.stale()
