"""Argument parsing (no git, no repo)."""

import pytest

import git_merge_onto as gmo


def test_parser_basic():
    args = gmo.build_parser().parse_args(["new", "old"])
    assert args.new == "new" and args.old == "old"
    assert args.message is None and args.quiet is False


def test_parser_flags():
    args = gmo.build_parser().parse_args(["-m", "msg", "--quiet", "develop", "feature"])
    assert args.new == "develop" and args.old == "feature"
    assert args.message == "msg" and args.quiet is True


def test_parser_requires_two_positionals():
    with pytest.raises(SystemExit):
        gmo.build_parser().parse_args(["only-one"])


def test_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        gmo.build_parser().parse_args(["--version"])
    assert excinfo.value.code == 0
    assert "git-merge-onto" in capsys.readouterr().out
