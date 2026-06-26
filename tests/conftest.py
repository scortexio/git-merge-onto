import pytest

import git_merge_onto as gmo
from _util import sh


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fresh git repo on `main`, with cwd moved into it and command echo silenced."""
    r = tmp_path / "repo"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@example.com")
    sh(r, "config", "user.name", "Test")
    sh(r, "config", "commit.gpgsign", "false")
    monkeypatch.chdir(r)
    monkeypatch.setattr(gmo, "VERBOSE", False)
    return r
