import pytest

from _util import sh


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fresh git repo on `main`, with cwd moved into it."""
    r = tmp_path / "repo"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@example.com")
    sh(r, "config", "user.name", "Test")
    sh(r, "config", "commit.gpgsign", "false")
    monkeypatch.chdir(r)
    return r
