# git-merge-onto

Re-parent a branch by merge instead of rebase. It is the `git merge` equivalent
of `git rebase --onto`: it moves your branch onto a new base and drops an old one,
without rewriting history and without a force-push.

```
git merge-onto <new> <old>
```

Run on the branch you want to move (`HEAD`). It performs a 3-way merge of `<new>`
into `HEAD` whose merge base is forced to `merge-base(HEAD, <old>)`. The result
keeps `HEAD`'s own changes, drops the content it shared with its old parent
`<old>`, and records `<new>` as a real ancestor. The new tip is a descendant of
the old one, so the branch updates as a fast-forward push.

## Why not just `git merge`?

A plain `git merge <new>` picks its base from the commit graph, and for a
re-parent that base is wrong in one of two ways:

- **Too low.** When `<new>` already contains `<old>`'s *content* but not its
  commit (the usual case after `<old>` was squash-merged into `<new>`), the
  natural base sits below `<old>`, so the merge re-applies `<old>` and conflicts
  on every hunk the squash reshaped. `-X ours` papers over this but also
  silently discards real changes that landed on `<new>`.
- **Too high.** When the new parent transitively contains `HEAD`'s own commit
  (a stack reorder), the natural base is `HEAD` itself, so the merge
  fast-forwards and silently drops your branch's change, leaving an empty diff.

Forcing the base to `merge-base(HEAD, <old>)` is correct in both. That base is
the one thing git porcelain cannot express, which is the whole reason this tool
exists.

## Install

```bash
# one-off, no install
uvx git-merge-onto <new> <old>

# or install so `git merge-onto` works as a git subcommand
uv tool install git-merge-onto
git merge-onto <new> <old>
```

It is a small, dependency-free Python package. Requires Python 3.9+ and git 2.13+.

## Example

You branched `feature` off `develop`, then branched `followup` off `feature`.
`feature` gets squash-merged into `develop`. Now move `followup` onto `develop`,
dropping `feature`, keeping `followup`'s own commits and its review history:

```bash
git switch followup
git merge-onto develop feature
git push            # fast-forward, no --force
gh pr edit followup --base develop
```

A clean merge commits straight away. A conflict is left in your working tree like
any merge: edit the files, `git add -A`, `git commit`.

## Flags

| flag | meaning |
|------|---------|
| `-m, --message <msg>` | commit message for a clean merge |
| `--absorbed` | record `<old>` as an extra parent (see below) |
| `--version` | print the version |

### `--absorbed`: mark the old parent as merged

By default the re-parent *drops* `<old>`: the result does not descend from its
tip, so git and GitHub keep treating `<old>` as unmerged. That is right when
you pull a branch out from under a live parent, and wrong when `<new>` already
carries `<old>`'s changes without its commits -- after a squash merge, a rebase
merge, or a cherry-pick. `--absorbed` asserts the latter: `<old>`'s tip is
recorded as an extra parent of the merge, so the result descends from it and
git and GitHub treat `<old>` as merged.

In the example above, with `git merge-onto --absorbed develop feature` the
re-homed `followup` contains `feature`, so its PR stays mergeable (and CI keeps
running) even while it is still based on `feature`, and GitHub shows `feature`
as merged into it. If `feature`'s tip is already an ancestor the extra parent
is redundant and git drops it, so the flag is safe to pass whenever the premise
holds.

This cannot be a default: whether `<old>`'s changes are already in `<new>` is a
fact about how `<old>` landed, not something visible in the commit graph. When
they are not (moving a branch off a live parent), the extra parent would
falsely mark `<old>` as merged into your branch.

## How it works

`git merge-onto <new> <old>` reduces to a single plumbing call:

```
git merge-recursive <merge-base(HEAD, old)> -- HEAD <new>
```

On a clean merge it writes the commit (parents `[HEAD, new]`) using the standard
`MERGE_HEAD` machinery, so resolving a conflict is just `git add` then
`git commit`, exactly like a normal merge. Nothing is rewritten and nothing is
force-pushed.

## Companion tools

`git-merge-onto` is the shared primitive behind two stacked-PR tools:

- [stack-mv](https://github.com/scortexio/gh-stack-mv) rearranges open PR stacks
  before they land (reorder, move between stacks, insert a prerequisite).
- [autorestack-action](https://github.com/Phlogistique/autorestack-action)
  re-homes descendant PRs after an ancestor lands.

Both re-parent by merge, never by rebase. This package isolates the one operation
git itself cannot do.
