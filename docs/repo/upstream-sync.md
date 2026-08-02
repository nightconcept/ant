# Upstream Sync Guide

Status: active
Last reviewed: 2026-08-01
Owner: theMackabu

How to pull `theMackabu/ant` (`upstream/master`) into this fork's protected
`main` without losing our work or silently inheriting a regression we cannot
explain.

For the named compliance suites and their bars, read
[compliance.md](compliance.md) first. This guide only covers the sync.

## The Shape Of The Problem

Upstream refactors aggressively, and our fork carries two kinds of commits:

- **Orthogonal work** — spec fixes, the JSON rewrite, CI, the compliance
  harness. These merge cleanly and should survive the sync intact.
- **Work in the same area upstream is rewriting** — mostly engine and async
  internals. When upstream replaces the machinery a commit of ours optimizes,
  git reports a content conflict, but the real decision is not hunk-by-hunk:
  it is *keep ours* or *drop ours as superseded*.

Getting that decision right is most of the work. The rest is making sure the
"did it get better or worse" measurement is actually trustworthy.

## The Playbook

### 1. See what is coming, and what it will hit

```
just upstream-status
```

Fetches upstream and prints the incoming commits, plus every file both sides
have touched since the merge base — each annotated with the commits *of ours*
that touched it. Read that annotation before starting the merge:

- A file listed with **one** of our commits is a keep-or-revert decision. If
  upstream rewrote the subsystem that commit optimizes, prefer reverting our
  commit first (step 2) over hand-merging it.
- A file listed with **several** unrelated commits of ours is a genuine
  hunk-by-hunk merge.

### 2. Revert what upstream supersedes, as its own commit

If an upstream commit replaces the mechanism one of our commits tunes, revert
ours *before* merging:

```
git revert --no-commit <our-sha>
```

Commit that separately, explaining which upstream commit supersedes it. The
merge that follows is then legible, and `git log` records why the optimization
went away instead of leaving it looking like a botched conflict resolution.

This is not a value judgement on our commit. Upstream's replacement is usually
a different design, not a better version of the same one — record what we lose.

### 3. Merge and resolve

```
git switch main
git pull --ff-only
git switch -c sync/upstream-<date>
git merge --no-commit --no-ff upstream/master
```

Resolve, then build. Two failure modes git will not warn about:

- **Symbols that vanished.** Upstream deleting an API our auto-merged code
  still calls does not conflict — it fails to compile. Grep for each API our
  reverted/kept commits introduced before trusting a clean merge.
- **Invariants carried by structure, not by text.** Upstream turning a builtin
  into a helper can silently drop something the old shape provided. The
  `Object.defineProperty` prologue is the worked example: our ToPropertyKey
  coercion relied on writing the coerced key back into the caller's *rooted*
  `args` array, and upstream's refactor left the helper with no `args` to write
  to — a GC hazard the compiler only surfaced because the write also stopped
  compiling. Ask what each conflicted hunk was *relying on*, not just what it
  said.

Record every resolution in the merge commit message.

### 4. Refresh the Nix vendor hash if the subproject set moved

Any wrap added or removed upstream changes what `ant-vendor` hashes over, and
neither side's checked-in hash is right once our fork also carries local wraps.
Set `outputHash = lib.fakeHash;` in `packages/nix/vendor.nix`, run
`nix build .#ant`, and take the `got:` hash from the mismatch error.

### 5. Measure — against one pinned corpus

**A fresh Test262 clone will lie to you.** The runner clones `tc39/test262` on
first use, so a new worktree gets a *newer* corpus than the tree you are
comparing against; the added tests then appear in the diff as failures the
merge "introduced". Both sides must read the same checkout.

```
just upstream-verify <sync-branch>
```

builds `upstream/master` standalone and the sync branch in throwaway worktrees,
both pinned to this checkout's corpus, and runs Test262 on all three points.
To do it by hand, `scripts/sync_upstream.py worktree` does the pinning (and
seeds the vendor cache so nothing re-downloads).

`upstream-status`'s companion, `sync_upstream.py attribute`, then takes the
three manifests and splits every new failure into:

- **inherited from upstream** — fails on `upstream/master` standalone too. We
  take it on by merging; it is not a resolution bug.
- **caused by our merge resolution** — upstream passes, we don't. It exits
  non-zero on any of these. Fix them before landing.

The three-way split matters because a merge can post a large net gain and still
hide a resolution bug inside it. Rate comparisons cannot tell the two apart;
only the failing-test *sets* can.

### 6. Land it through the protected route

Ant Regression must pass. Test262 must show no failure that
`attribute` blames on us. Inherited upstream regressions are a judgement call —
they are usually worth accepting to stay close to upstream, but list them
explicitly in the merge commit or PR so they are not discovered later as ours.

Push the sync branch and open a pull request to `main`. The required `PR Gate`
must pass; do not push the merge directly to `main`.

## What A Sync Is Not

Do not "clean up" upstream's code as part of the merge, and do not fold our own
fixes into the merge commit. A sync that contains only reverts, resolutions,
and a hash refresh can be re-done from scratch if it goes wrong. One that also
carries new work cannot.

Fixes for inherited upstream regressions belong in follow-up commits — and,
per [compliance.md](compliance.md), in a shape small enough to send upstream.

## Related

- Compliance suites and the definition of done: [compliance.md](compliance.md)
- Validation scope: [testing.md](testing.md)
- Branch layout (`main` / `upstream`): [../../AGENTS.md](../../AGENTS.md).
  Note that `upstream` is a record of `theMackabu/ant`'s work kept for history
  and inspection; "upstreamable" is `main`'s standard.
