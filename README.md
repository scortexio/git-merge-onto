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
| `--quiet` | do not echo the executed git commands |
| `--version` | print the version |

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
