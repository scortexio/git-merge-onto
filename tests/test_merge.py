"""Behavioral tests against real git repos: the three re-parent regimes, conflict
handling, and the precondition guards."""

import subprocess

import pytest

import git_merge_onto as gmo
from _util import commit_file, is_ancestor, out, parents, rc, sh, txt_files


def test_reparent_drops_old_content(repo):
    # main <- a <- b. Move b onto main, dropping a.
    commit_file(repo, "base.txt", "base\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    b_old = commit_file(repo, "b.txt", "B\n", "b")

    assert gmo.merge_onto("main", "a") is True

    assert not (repo / "a.txt").exists()             # old parent's content dropped
    assert (repo / "b.txt").read_text() == "B\n"     # own change kept
    assert out(repo, "diff", "--name-only", "main", "HEAD") == "b.txt"
    assert is_ancestor(repo, b_old, "HEAD")          # fast-forward push (no --force)
    assert is_ancestor(repo, "main", "HEAD")         # new parent is a real ancestor
    # main was already an ancestor of b, so git drops the redundant second parent: a
    # single-parent commit whose tree drops a is exactly right (nothing to record).
    assert len(parents(repo)) == 1


def test_reparent_onto_descendant_of_old(repo):
    # main <- a, with a <- b and a <- c (a fork). Move c onto b. Here the new parent
    # b already contains the old parent a as a real ancestor, so git's own merge base
    # equals the forced one and a plain merge would also work.
    commit_file(repo, "base.txt", "base\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    sh(repo, "switch", "-q", "-c", "c", "a")
    commit_file(repo, "c.txt", "C\n", "c")

    assert gmo.merge_onto("b", "a") is True

    assert (repo / "c.txt").read_text() == "C\n"
    assert (repo / "b.txt").read_text() == "B\n"
    assert (repo / "a.txt").read_text() == "A\n"
    assert out(repo, "diff", "--name-only", "b", "HEAD") == "c.txt"


def test_down_move_forced_base_preserves_delta(repo):
    # main <- a <- b <- c, reordered to main <- c <- a <- b. The interesting rebuild is
    # b's: the rebuilt parent a transitively contains b's own commit, so a plain merge
    # would take b as the base and fast-forward, silently dropping b's change. The forced
    # base (b's old parent) keeps it.
    commit_file(repo, "base.txt", "base\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    a_old = commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    b_old = commit_file(repo, "b.txt", "B\n", "b")
    sh(repo, "switch", "-q", "-c", "c")
    commit_file(repo, "c.txt", "C\n", "c")

    # 1) c onto main, dropping its old parent b.
    sh(repo, "switch", "-q", "c")
    assert gmo.merge_onto("main", b_old) is True
    assert txt_files(repo) == ["base.txt", "c.txt"]

    # 2) a onto the rebuilt c, dropping main.
    sh(repo, "switch", "-q", "a")
    assert gmo.merge_onto("c", "main") is True

    # The trap, made visible: the rebuilt a reaches b's old commit, so a plain merge of
    # a into b fast-forwards and the b.txt change vanishes.
    assert is_ancestor(repo, b_old, "a")
    sh(repo, "switch", "-q", "-c", "b_plain", b_old)
    sh(repo, "merge", "-q", "--no-edit", "a")
    assert not (repo / "b.txt").exists()

    # 3) merge-onto forces the base to b's old parent, so b's change survives.
    sh(repo, "switch", "-q", "b")
    assert gmo.merge_onto("a", a_old) is True
    assert (repo / "b.txt").read_text() == "B\n"
    assert txt_files(repo) == ["a.txt", "b.txt", "base.txt", "c.txt"]
    assert out(repo, "diff", "--name-only", "a", "HEAD") == "b.txt"  # PR diff is just b


def test_squash_regime_clean_where_plain_merge_conflicts(repo):
    # feature is squash-merged into develop: develop carries feature's content, reshaped,
    # without feature's commit as an ancestor. Re-homing followup onto develop must drop
    # feature without re-applying it. A plain merge add/add-conflicts; merge-onto does not.
    commit_file(repo, "base.txt", "base\n", "main")
    sh(repo, "switch", "-q", "-c", "feature")
    commit_file(repo, "shared.txt", "v1\n", "feature")
    sh(repo, "switch", "-q", "-c", "followup")
    commit_file(repo, "followup.txt", "F\n", "followup")
    sh(repo, "switch", "-q", "-c", "develop", "main")
    commit_file(repo, "shared.txt", "v1-squashed\n", "squash of feature")

    # Plain merge: add/add conflict on shared.txt.
    sh(repo, "switch", "-q", "-c", "followup_plain", "followup")
    assert rc(repo, "merge", "--no-edit", "develop") != 0
    assert "<<<<<<<" in (repo / "shared.txt").read_text()
    sh(repo, "merge", "--abort")

    # merge-onto: clean, adopting develop's version of the shared content.
    sh(repo, "switch", "-q", "followup")
    assert gmo.merge_onto("develop", "feature") is True
    assert (repo / "shared.txt").read_text() == "v1-squashed\n"
    assert (repo / "followup.txt").read_text() == "F\n"
    assert out(repo, "diff", "--name-only", "develop", "HEAD") == "followup.txt"
    # develop is not an ancestor of followup, so it is recorded as a real second parent.
    assert len(parents(repo)) == 2 and out(repo, "rev-parse", "develop") in parents(repo)


def test_conflict_left_in_progress_then_resolved(repo):
    # Move b onto `other` (a sibling off main), dropping a. b and other touch the same
    # line, so the re-parent conflicts; other is not an ancestor of b, so the resolved
    # commit is a real two-parent merge.
    commit_file(repo, "f.txt", "1\n2\n3\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "f.txt", "1\nA\n3\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    b_old = commit_file(repo, "f.txt", "1\nB\n3\n", "b")
    sh(repo, "switch", "-q", "-c", "other", "main")
    other = commit_file(repo, "f.txt", "1\nO\n3\n", "other")
    sh(repo, "switch", "-q", "b")

    assert gmo.merge_onto("other", "a") is False
    assert gmo.in_progress_merge()
    assert "<<<<<<<" in (repo / "f.txt").read_text()

    # Resolve like any merge: edit, add, commit.
    (repo / "f.txt").write_text("1\nB\n3\n")
    sh(repo, "add", "f.txt")
    sh(repo, "commit", "--no-edit")

    assert not gmo.in_progress_merge()
    ps = parents(repo)
    assert b_old in ps and other in ps


def test_noop_skip_makes_no_commit(repo):
    # Re-parent b onto a, dropping a: tree unchanged and a is already an ancestor, so no
    # merge commit is created.
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    b_old = commit_file(repo, "b.txt", "B\n", "b")

    assert gmo.merge_onto("a", "a") is True
    assert out(repo, "rev-parse", "HEAD") == b_old


def test_custom_message(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")

    assert gmo.merge_onto("main", "a", message="custom subject") is True
    assert out(repo, "log", "-1", "--format=%s") == "custom subject"


def test_refuses_dirty_tree(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    (repo / "dirty.txt").write_text("uncommitted\n")

    with pytest.raises(gmo.UserError, match="not clean"):
        gmo.merge_onto("main", "a")
    assert not gmo.in_progress_merge()


def test_refuses_when_merge_in_progress(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    (gmo.git_dir() / "MERGE_HEAD").write_text(out(repo, "rev-parse", "main") + "\n")

    with pytest.raises(gmo.UserError, match="already in progress"):
        gmo.merge_onto("main", "a")


def test_rejects_unknown_refs(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")

    with pytest.raises(gmo.UserError, match="old parent"):
        gmo.merge_onto("main", "nope")
    with pytest.raises(gmo.UserError, match="not a valid commit"):
        gmo.merge_onto("nope", "main")


def test_no_common_ancestor(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    sh(repo, "switch", "-q", "--orphan", "island")
    island = commit_file(repo, "island.txt", "I\n", "island")
    sh(repo, "switch", "-q", "b")

    with pytest.raises(gmo.UserError, match="no common ancestor"):
        gmo.merge_onto("main", island)


def test_merge_with_base_raises_on_bad_base(repo):
    # A base that is not a real object makes merge-recursive refuse (rc > 1).
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    zero = "0" * 40
    with pytest.raises(gmo.CommandError):
        gmo.merge_with_base(zero, out(repo, "rev-parse", "main"), "msg")


def test_main_clean_returns_0(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "a.txt", "A\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    assert gmo.main(["--quiet", "main", "a"]) == 0


def test_main_conflict_returns_1(repo):
    commit_file(repo, "f.txt", "1\n2\n3\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "f.txt", "1\nA\n3\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "f.txt", "1\nB\n3\n", "b")
    assert gmo.main(["--quiet", "main", "a"]) == 1


def test_main_bad_ref_returns_2(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    assert gmo.main(["main", "nope"]) == 2


def test_forced_base_when_old_parent_advanced(repo):
    # b forked from a at a1 (shared=v1). Branch a then advances: a2 sets shared=v2. The
    # base must be merge-base(b, a)=a1, NOT a's current tip a2. With a1 as base, b never
    # modified shared (v1==v1), so main's deletion of it applies cleanly; with a2 as base
    # it is a modify/delete conflict. This is the only test where merge-base(HEAD, old)
    # differs from old, so it is what makes the forced-base computation load-bearing.
    commit_file(repo, "base.txt", "base\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "shared.txt", "v1\n", "a1")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    sh(repo, "switch", "-q", "a")
    commit_file(repo, "shared.txt", "v2\n", "a2 advances a past b's fork point")
    sh(repo, "switch", "-q", "b")

    assert gmo.merge_onto("main", "a") is True       # clean, not a modify/delete conflict
    assert not gmo.in_progress_merge()
    assert not (repo / "shared.txt").exists()         # old parent's content dropped
    assert (repo / "b.txt").read_text() == "B\n"      # own change kept
    assert out(repo, "diff", "--name-only", "main", "HEAD") == "b.txt"


def test_clean_merge_when_tree_unchanged_but_new_not_ancestor(repo):
    # develop carries shared content byte-identical to feature, so the merged tree equals
    # HEAD's existing tree. The skip must NOT fire, because develop is not an ancestor: a
    # real two-parent merge has to be recorded, or the PR head never reaches its new base.
    commit_file(repo, "base.txt", "base\n", "main")
    sh(repo, "switch", "-q", "-c", "feature")
    commit_file(repo, "shared.txt", "v1\n", "feature")
    sh(repo, "switch", "-q", "-c", "followup")
    fu_old = commit_file(repo, "followup.txt", "F\n", "followup")
    sh(repo, "switch", "-q", "-c", "develop", "main")
    commit_file(repo, "shared.txt", "v1\n", "develop with identical shared content")
    sh(repo, "switch", "-q", "followup")

    old_tree = out(repo, "rev-parse", "HEAD^{tree}")
    assert gmo.merge_onto("develop", "feature") is True
    assert out(repo, "rev-parse", "HEAD") != fu_old             # a commit was made
    assert out(repo, "rev-parse", "HEAD^{tree}") == old_tree    # even though the tree is unchanged
    ps = parents(repo)
    assert len(ps) == 2 and out(repo, "rev-parse", "develop") in ps
    assert is_ancestor(repo, "develop", "HEAD")                 # new base is now reachable


def test_refuses_during_rebase(repo):
    commit_file(repo, "f.txt", "1\n", "c0")
    commit_file(repo, "f.txt", "2\n", "c1")
    commit_file(repo, "f.txt", "3\n", "c2")
    # Pause a rebase with a failing --exec: clean tree, detached HEAD, rebase-merge present.
    subprocess.run(["git", "rebase", "--exec", "false", "HEAD~2"], cwd=str(repo), capture_output=True)
    assert (gmo.git_dir() / "rebase-merge").is_dir()
    assert not gmo.worktree_dirty()  # the guard's blind spot: clean tree, op in progress

    with pytest.raises(gmo.UserError, match="rebase"):
        gmo.merge_onto("HEAD", "HEAD")  # refs are irrelevant; the guard fires first
    sh(repo, "rebase", "--abort")


@pytest.mark.parametrize("marker,name", [("CHERRY_PICK_HEAD", "cherry-pick"), ("REVERT_HEAD", "revert")])
def test_refuses_during_sequencer_op(repo, marker, name):
    commit_file(repo, "f.txt", "x\n", "main")
    sh(repo, "switch", "-q", "-c", "b")
    commit_file(repo, "b.txt", "B\n", "b")
    (gmo.git_dir() / marker).write_text(out(repo, "rev-parse", "main") + "\n")

    with pytest.raises(gmo.UserError, match=name):
        gmo.merge_onto("main", "b")


def test_resolve_commit_origin_fallback(repo):
    commit_file(repo, "f.txt", "x\n", "main")
    target = out(repo, "rev-parse", "main")
    # A remote-tracking ref with no matching local branch: resolved via the origin/ DWIM.
    sh(repo, "update-ref", "refs/remotes/origin/feature", target)
    assert gmo._resolve_commit("feature") == target
    assert gmo._resolve_commit("nope") is None


def test_merge_abort_recovers_from_conflict(repo):
    # The conflict message points the user at `git merge --abort`; it works only because
    # the markers include ORIG_HEAD and MERGE_MODE, not just MERGE_HEAD/MERGE_MSG.
    commit_file(repo, "f.txt", "1\n2\n3\n", "main")
    sh(repo, "switch", "-q", "-c", "a")
    commit_file(repo, "f.txt", "1\nA\n3\n", "a")
    sh(repo, "switch", "-q", "-c", "b")
    b_old = commit_file(repo, "f.txt", "1\nB\n3\n", "b")
    sh(repo, "switch", "-q", "-c", "other", "main")
    commit_file(repo, "f.txt", "1\nO\n3\n", "other")
    sh(repo, "switch", "-q", "b")

    assert gmo.merge_onto("other", "a") is False
    assert gmo.in_progress_merge()

    sh(repo, "merge", "--abort")
    assert not gmo.in_progress_merge()
    assert out(repo, "rev-parse", "HEAD") == b_old
    assert (repo / "f.txt").read_text() == "1\nB\n3\n"
    assert not gmo.worktree_dirty()
