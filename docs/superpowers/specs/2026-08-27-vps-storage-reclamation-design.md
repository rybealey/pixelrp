# VPS Storage Reclamation + Build-Cache Guardrail

**Date:** 2026-08-27
**Branch:** `beta` (git edits only; live-box actions are branch-agnostic)
**Scope:** Subsystem #1 of the larger furni/catalog epic. Storage only — no furni or catalog work here.

## Problem

The PixelRP VPS (`67.219.109.182`) root filesystem is **80% full: 71 G used of 94 G, 19 G free**.
Diagnosis showed the space is **not** where it was assumed to be:

- `/var` = 56 G, almost entirely the **Docker build cache: 53.84 GB across 975 layers, 47.74 GB reclaimable.**
  It regrew this large because **nothing ever prunes it** — every deploy runs `$COMPOSE build emulator cms`
  on the box and none of the resulting cache is reclaimed.
- The arcturus backup (`/opt/pixelrp-arcturus-old`, 884 M) is real but negligible next to the cache.
- Every container maps to prod (`pixelrp-*`) or beta (`pixelrp-beta-*`). There are **no orphaned/stale
  third-party containers.** The prod stack is *stopped* (Exited 3 days ago) except its DB, but those are
  "main branch" containers the user asked to retain.

## Goals

1. Reclaim disk safely, now.
2. Prevent the build cache from ballooning back to ~54 G.
3. Touch nothing associated with the prod (`main`) or beta stacks.

## Non-goals

- No changes to furni, catalog, DB rows, or game data (later subsystems).
- Do **not** delete/modify any container, tagged image, volume, the swapfile, or the current
  deploy-DB snapshots in `/opt/pixelrp-backups` (93 M, kept per user decision).
- Do not attempt to start/repair the stopped prod stack (out of scope; prod is intentionally on hold).

## Design

### Part A — One-time purge (live box)

Run over SSH, in order, capturing `df -h /` before and after:

1. `docker builder prune -f` — unused build cache. Expected reclaim ~47.7 G.
   *Safe:* touches no container/image, only slows the next rebuild (cold cache).
2. `docker image prune -f` — dangling (untagged) layers only. Expected ~0.5 G.
   *Safe:* Docker refuses to remove any image referenced by a container, running or stopped, so the
   retained prod/beta images are protected; tagged images are never touched by `image prune`.
3. `rm -rf /opt/pixelrp-arcturus-old /root/pixelrp-backup-20260807` — arcturus backup. ~0.9 G.
   *Authorized by user.* Safety net: the old RP work also lives on the `rybealey/atomcms` fork's `main`
   branch (per project memory). Verify the two paths' contents immediately before `rm`.

**Expected result:** ~49 G freed → ~22 G used (~24%). Verify with `docker system df` and `df -h /`.

### Part B — Guardrail (git edit, beta branch)

Add a final step to **both** `.github/workflows/deploy.yml` and `.github/workflows/deploy-beta.yml`,
after the stack is confirmed up (`up -d` succeeded, health verified), inside the existing SSH block:

```bash
# Cap the BuildKit cache so it can't balloon again; keeps recent layers for fast rebuilds.
docker builder prune -f --max-used-space 10GB || true
```

- Placed **at the end** so a failed build keeps its cache for a fast retry.
- Box runs **Docker 29.7.1**, where `--keep-storage` is removed; the correct flag is
  `--max-used-space 10GB`, which prunes the cache down to at most 10 G (evicting LRU first).
- `|| true` so a prune hiccup never fails an otherwise-successful deploy.
- Both edits land on `beta`; the `deploy.yml` (prod) change simply waits there until a later merge to `main`.

## Verification

- **Part A:** `df -h /` shows ~49 G freed; `docker system df` shows build cache back near 0 and reclaimable
  low; `docker ps -a` still lists all 9 prod+beta containers unchanged; beta site still responds.
- **Part B:** `git diff` shows the added step in both workflow files; YAML still parses (indentation);
  no other workflow lines changed.

## Rollback

- Part A is not reversible (that's the point) but is non-destructive to anything running: images rebuild
  from source on the next deploy; the arcturus copy remains on the atomcms fork.
- Part B: revert the two-line workflow additions.

## Execution order

1. Snapshot `df -h /` + `docker system df`.
2. Purge steps 1→2→3, re-checking `df -h /` after.
3. Confirm all prod+beta containers intact and beta site up.
4. Edit both workflows on `beta`, commit, push (auto-deploys beta — acceptable; guardrail self-tests).
5. Update project memory (arcturus backup removed; build-cache guardrail added).
