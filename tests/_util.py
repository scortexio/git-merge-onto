"""Helpers for driving a real git repo in tests."""

import subprocess


def sh(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(repo), text=True, capture_output=True, check=check
    )


def out(repo, *args):
    return sh(repo, *args).stdout.strip()


def rc(repo, *args):
    return sh(repo, *args, check=False).returncode


def commit_file(repo, name, content, msg):
    (repo / name).write_text(content)
    sh(repo, "add", name)
    sh(repo, "commit", "-q", "-m", msg)
    return out(repo, "rev-parse", "HEAD")


def parents(repo, ref="HEAD"):
    fields = out(repo, "rev-list", "--parents", "-n", "1", ref).split()
    return fields[1:]  # drop the commit's own sha, keep its parents


def is_ancestor(repo, ancestor, descendant):
    return rc(repo, "merge-base", "--is-ancestor", ancestor, descendant) == 0


def txt_files(repo):
    return sorted(p.name for p in repo.glob("*.txt"))
