# Trailing Re-engage Unblock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the one-tile trailing acquire after formation turnarounds by (1) lifting the re-engage hysteresis when a released pair re-proves a shared route in a different direction and (2) admitting exactly-one-tile pairs through the engage proximity gate.

**Architecture:** All changes live in one file of the client's patched nitro-renderer — `client/node_modules/@nitrots/nitro-renderer/src/room/renderer/RoomSpriteCanvas.ts` — which is a *working copy*: the tracked artifact is the yarn patch `client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch`, resealed after editing. The plus repo then gets a CHANGELOG entry and a submodule bump on `feat/pathfinder`, PR'd to `beta`.

**Tech Stack:** TypeScript (vendored renderer), yarn v4 `patch:` protocol, vite. No unit-test harness exists for the vendored renderer — verification is: tsc baseline comparison, vite build, patch-integrity ritual, and manual in-game testing (the project's established practice; the `[sync:*]` console diagnostics are the test instrument).

**Spec:** `docs/superpowers/specs/2026-08-27-trailing-reengage-unblock-design.md`

## Global Constraints

- Client submodule work happens on a new branch `feat/pathfinder` created from `pixelrp` @ `8fa809b3`.
- tsc baseline: `npx tsc --noEmit` currently reports EXACTLY 2 pre-existing errors (both `Property 'motto' does not exist on type 'ISessionDataManager'`). The bar everywhere is "no NEW errors", not zero.
- CRITICAL SEQUENCING: run `yarn install --immutable` BEFORE editing `node_modules` (baseline sync), and do NOT run any `yarn install` between editing and `yarn patch-commit` — an install regenerates `node_modules` from the OLD patch and silently discards the edits.
- The engage proximity bound must never exceed the maintenance bound `(1 + 1e-6)` (see spec — wider bounds cause engage→release thrash).
- Player-facing text (CHANGELOG body): plain hyphens, no em-dashes, player language (no code names). Code comments may use the file's existing em-dash style.
- Every commit ends with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Push the client branch BEFORE the plus bump commit that references it (submodule pointer reachability).
- Scratch space: use `/private/tmp/claude-501/-Users-rybealey-Documents-Personal-pixelrp-plus/5759f8ce-e01b-4a43-a376-900d18de2b11/scratchpad` (referred to as `$SCRATCH` below) for verification artifacts, never the repos.
- Line numbers cited below were verified against `8fa809b3` and are advisory — always match by the exact code text given in each step.

---

### Task 1: Code changes in the patched renderer (working copy)

**Files:**
- Modify: `client/node_modules/@nitrots/nitro-renderer/src/room/renderer/RoomSpriteCanvas.ts` (4 edits + 1 comment fix)

**Interfaces:**
- Consumes: existing `_pixelrpLastReleased` field, `samePathWith` closure, `stepGoalX/stepGoalY/stepStartX/stepStartY` locals, `sync.lockedDirX/lockedDirY` (all already in `renderObject()`).
- Produces: `_pixelrpLastReleased` gains `dirX: number, dirY: number` (NaN allowed); new console diagnostic `[sync:REENGAGE_UNBLOCKED]`; engage gate accepts Chebyshev `<= 1 + 1e-6`. Task 2 reseals exactly these bytes into the yarn patch.

- [ ] **Step 1: Create the client branch and sync the baseline**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/client
git checkout -b feat/pathfinder 8fa809b3
yarn install --immutable
npx tsc --noEmit 2>&1 | grep -c "error TS"
```

Expected: branch created; install succeeds with no lockfile changes; tsc error count is exactly `2` (the two known `motto` errors). If the count differs, STOP and report — the baseline assumption is wrong.

- [ ] **Step 2: Edit A — field declaration + comment (around line 399)**

In `node_modules/@nitrots/nitro-renderer/src/room/renderer/RoomSpriteCanvas.ts`, replace this exact block:

```ts
    // release was supposed to end. sawSeparated latches true the first
    // time, after release, the pair's distance genuinely exceeds the
    // engage proximity gate (<1 tile) — i.e. real evidence they've
    // completed the crossing/separated — which is the primary proof;
    // the 3000ms window is only a backstop for the case they never
    // visibly separate (e.g. end up standing still near each other).
    // Scoped to this one pair via pairKey; unrelated pairs are
    // unaffected. blockLogged avoids repeating the same diagnostic
    // line every frame while the block remains active.
    private _pixelrpLastReleased: { pairKey: string, at: number, sawSeparated: boolean, blockLogged: boolean } = null;
```

with:

```ts
    // release was supposed to end. sawSeparated latches true the first
    // time, after release, the pair's distance genuinely exceeds a
    // full tile on some axis (the stillClose test in the hysteresis
    // check) — i.e. real evidence they've
    // completed the crossing/separated — which is the primary proof;
    // the 3000ms window is only a backstop for the case they never
    // visibly separate (e.g. end up standing still near each other).
    // Scoped to this one pair via pairKey; unrelated pairs are
    // unaffected. blockLogged avoids repeating the same diagnostic
    // line every frame while the block remains active.
    // dirX/dirY: the released session's last CONFIRMED shared walk
    // direction (sync.lockedDirX/Y at release; NaN if the session never
    // confirmed one). A pair that re-proves a shared route in a
    // DIFFERENT direction (a turnaround — the pair reversed and
    // re-formed) is a NEW relationship, not the old crossing
    // continuing, so it unblocks immediately instead of waiting out
    // the backstop — see the direction-aware unblock in the
    // hysteresis check in renderObject().
    private _pixelrpLastReleased: { pairKey: string, at: number, sawSeparated: boolean, blockLogged: boolean, dirX: number, dirY: number } = null;
```

- [ ] **Step 3: Edit B — record the release direction (around line 2157)**

Replace this exact line:

```ts
                    this._pixelrpLastReleased = { pairKey: this.pixelrpPairKey(sync.masterId, sync.joinerId), at: nowMs, sawSeparated: false, blockLogged: false };
```

with:

```ts
                    this._pixelrpLastReleased = { pairKey: this.pixelrpPairKey(sync.masterId, sync.joinerId), at: nowMs, sawSeparated: false, blockLogged: false, dirX: sync.lockedDirX, dirY: sync.lockedDirY };
```

(This is the only construction site of `_pixelrpLastReleased` in the file — verify with `grep -c "this._pixelrpLastReleased = {" node_modules/@nitrots/nitro-renderer/src/room/renderer/RoomSpriteCanvas.ts` → expect `1`.)

- [ ] **Step 4: Edit C — direction-aware unblock in the hysteresis check (around line 1041)**

Replace this exact block:

```ts
                if(!this._pixelrpLastReleased.sawSeparated)
                {
                    const stillClose = ((Math.abs(roomLocation.x - own.tx) < 1) && (Math.abs(roomLocation.y - own.ty) < 1));

                    if(!stillClose) this._pixelrpLastReleased.sawSeparated = true;
                }
```

with:

```ts
                if(!this._pixelrpLastReleased.sawSeparated)
                {
                    const stillClose = ((Math.abs(roomLocation.x - own.tx) < 1) && (Math.abs(roomLocation.y - own.ty) < 1));

                    if(!stillClose) this._pixelrpLastReleased.sawSeparated = true;
                    else if(Number.isFinite(this._pixelrpLastReleased.dirX) && samePathWith(own))
                    {
                        // Direction-aware unblock: the pair is still close, but
                        // it has re-proven a shared route (samePathWith requires
                        // both sides mid-step with IDENTICAL step directions) in
                        // a direction DIFFERENT from the one the released
                        // session had confirmed. That is a turnaround re-forming
                        // the pair — a NEW route relationship — not the
                        // crossing/overtake release loop this hysteresis exists
                        // to suppress (a loop keeps the SAME direction). Treat
                        // it as separation-grade proof so ENGAGE can fire this
                        // same frame, while the pair is still catchable
                        // (<1 tile apart). Without this, the full 3000ms
                        // backstop always elapsed here — sawSeparated needs a
                        // >=1-tile observation, which a pair that is FORMING UP
                        // can never produce — and the entire acquire window was
                        // consumed rendering pure native (confirmed
                        // frame-by-frame from the 2026-08-28 turnaround clip).
                        const sharedDirX = (stepGoalX - stepStartX);
                        const sharedDirY = (stepGoalY - stepStartY);

                        if((sharedDirX !== this._pixelrpLastReleased.dirX) || (sharedDirY !== this._pixelrpLastReleased.dirY))
                        {
                            this._pixelrpLastReleased.sawSeparated = true;

                            console.log(`[sync:REENGAGE_UNBLOCKED] reason=direction_change pairKey=${ this._pixelrpLastReleased.pairKey } releasedDir=(${ this._pixelrpLastReleased.dirX },${ this._pixelrpLastReleased.dirY }) newDir=(${ sharedDirX },${ sharedDirY }) sinceReleaseMs=${ nowMs - this._pixelrpLastReleased.at }`);
                        }
                    }
                }
```

Scope notes for the implementer: `stepGoalX/stepGoalY/stepStartX/stepStartY` are function locals defined earlier in `renderObject()` (the per-unit step bookkeeping); when `samePathWith(own)` returns non-null, the remote unit is mid-step, so these are integers ≥ 0 and the subtraction gives the shared direction (samePathWith already requires both sides' directions to be identical). `sawSeparated = true` permanently lifts the block for this record, same as the existing separation path — that is intended.

- [ ] **Step 5: Edit D — engage proximity gate (around line 1004) + stale comment (around line 990)**

Replace this exact line (inside `samePathWith`):

```ts
                if(!((Math.abs(roomLocation.x - other.tx) < 1) && (Math.abs(roomLocation.y - other.ty) < 1))) return null;
```

with:

```ts
                // Proximity gate: <= 1 tile (+epsilon), matching the
                // maintenance pathOk distance bound EXACTLY. The old strict
                // <1 made a pair whose native gap had already reached a full
                // tile (e.g. the server's walk-grid slew finished forming
                // them while no session was active) permanently
                // unengageable — never captured, never locked, never
                // correctable. At exactly 1.0 the engage flows into the
                // lateEntry acquire with requiredTravel ~0: an instant
                // spacing lock, no hold. The bound must never exceed
                // maintenance's (1 + 1e-6): engaging a pair maintenance
                // would reject just thrashes engage->release and re-arms
                // the re-engagement hysteresis.
                if(!((Math.abs(roomLocation.x - other.tx) <= (1 + 1e-6)) && (Math.abs(roomLocation.y - other.ty) <= (1 + 1e-6)))) return null;
```

Then replace this exact stale comment block (in the doc comment above `samePathWith`):

```ts
            // JOINER once roles are assigned below. Still gated on <1 tile
            // overlap on both axes — keeps opposite-side converging units
            // from sticking before they truly overlap; this proximity gate
            // is the system's actual scope and is unchanged.
```

with:

```ts
            // JOINER once roles are assigned below. Still gated on
            // proximity on both axes (<= 1 tile + epsilon, matching the
            // maintenance bound — see the gate comment below) — keeps
            // opposite-side converging units from sticking before they
            // truly overlap; this proximity gate is the system's scope.
```

- [ ] **Step 6: Verify tsc — no new errors**

```bash
npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: EXACTLY the same 2 `motto` errors as Step 1, nothing else. Any new error means an edit is malformed — fix before proceeding.

- [ ] **Step 7: Verify vite build**

```bash
yarn build
```

Expected: build completes with exit code 0 (warnings about chunk size are normal).

---

### Task 2: Reseal the yarn patch, verify integrity, commit and push the client branch

**Files:**
- Modify: `client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch` (regenerated)
- Modify: `client/yarn.lock` (patch content hash refresh)

**Interfaces:**
- Consumes: the edited `node_modules` tree from Task 1 (do NOT run `yarn install` before Step 2's `patch-commit` — it would discard those edits).
- Produces: a pushed client commit on `feat/pathfinder` whose SHA Task 3 bumps into the plus repo.

- [ ] **Step 1: Extract the patched-file list and open a pristine patch workspace**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/client
SCRATCH=/private/tmp/claude-501/-Users-rybealey-Documents-Personal-pixelrp-plus/5759f8ce-e01b-4a43-a376-900d18de2b11/scratchpad
grep '^diff --git' .yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch | sed 's|diff --git a/||; s| b/.*||' > "$SCRATCH/patched-files.txt"
wc -l "$SCRATCH/patched-files.txt"
cp .yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch "$SCRATCH/patch-before.patch"
yarn patch @nitrots/nitro-renderer@npm:1.6.6
```

Expected: the file list has 30-40 entries, all under `src/`; `yarn patch` prints a temp directory path (e.g. `/private/var/folders/.../T/xfs-.../user`) and the matching `yarn patch-commit` command. Record that path as `$PATCHDIR` for the next steps.

- [ ] **Step 2: Overlay every patched file from node_modules onto the pristine workspace**

```bash
while IFS= read -r f; do
  mkdir -p "$PATCHDIR/$(dirname "$f")"
  cp "node_modules/@nitrots/nitro-renderer/$f" "$PATCHDIR/$f"
done < "$SCRATCH/patched-files.txt"
grep -c "REENGAGE_UNBLOCKED" "$PATCHDIR/src/room/renderer/RoomSpriteCanvas.ts"
```

Expected: copy loop silent; the grep prints `1` (the edits made it into the workspace).

- [ ] **Step 3: Commit the patch and refresh the lockfile hash**

```bash
yarn patch-commit -s "$PATCHDIR"
git diff --stat package.json
yarn install
git status --short
```

Expected: `package.json` shows NO diff (the patch path is unchanged, so the resolution string is identical); after `yarn install`, `git status` shows exactly two modified files: `.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch` and `yarn.lock` (the `hash=` parameter in the nitro-renderer patch resolution changed). Any other modified file is a red flag — investigate before continuing.

- [ ] **Step 4: Verify the new patch touches ONLY RoomSpriteCanvas.ts hunks**

Per-file hunk comparison against the pre-reseal patch (this is the reseal trap: verify per-file CONTENT, not just the file list):

```bash
python3 - <<'EOF'
import re, sys
SCRATCH = "/private/tmp/claude-501/-Users-rybealey-Documents-Personal-pixelrp-plus/5759f8ce-e01b-4a43-a376-900d18de2b11/scratchpad"
def split(path):
    files, cur, name = {}, [], None
    for line in open(path):
        m = re.match(r'^diff --git a/(\S+) ', line)
        if m:
            if name: files[name] = ''.join(cur)
            name, cur = m.group(1), []
        cur.append(line)
    if name: files[name] = ''.join(cur)
    return files
old = split(f"{SCRATCH}/patch-before.patch")
new = split("/Users/rybealey/Documents/Personal/pixelrp/plus/client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch")
assert set(old) == set(new), f"file list changed: only-old={set(old)-set(new)} only-new={set(new)-set(old)}"
changed = [f for f in old if old[f] != new[f]]
print("files with changed hunks:", changed)
assert changed == ["src/room/renderer/RoomSpriteCanvas.ts"], "UNEXPECTED files changed!"
print("OK: only RoomSpriteCanvas.ts hunks changed")
EOF
```

Expected: `OK: only RoomSpriteCanvas.ts hunks changed`. If other files appear, the overlay copied a stale or locally-drifted file — STOP and diff those files against `patch-before.patch` expectations before continuing.

- [ ] **Step 5: Verify the resealed patch round-trips and node_modules carries the edits**

```bash
grep -c "REENGAGE_UNBLOCKED" node_modules/@nitrots/nitro-renderer/src/room/renderer/RoomSpriteCanvas.ts
rm -rf "$SCRATCH/roundtrip" && mkdir -p "$SCRATCH/roundtrip"
cp -R node_modules/@nitrots/nitro-renderer/src "$SCRATCH/roundtrip/src"
cd "$SCRATCH/roundtrip"
git apply -R --check /Users/rybealey/Documents/Personal/pixelrp/plus/client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch && echo "reverse-apply OK"
git apply -R /Users/rybealey/Documents/Personal/pixelrp/plus/client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch
git apply --check /Users/rybealey/Documents/Personal/pixelrp/plus/client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch && echo "forward-apply OK"
git apply /Users/rybealey/Documents/Personal/pixelrp/plus/client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch
diff -r src /Users/rybealey/Documents/Personal/pixelrp/plus/client/node_modules/@nitrots/nitro-renderer/src && echo "BYTE-IDENTICAL"
cd /Users/rybealey/Documents/Personal/pixelrp/plus/client
```

Expected: first grep prints `1` (post-install node_modules was rebuilt FROM the new patch and still contains the change); then `reverse-apply OK`, `forward-apply OK`, `BYTE-IDENTICAL`.

- [ ] **Step 6: Final immutable-install, tsc, and build checks**

```bash
yarn install --immutable
npx tsc --noEmit 2>&1 | grep "error TS"
yarn build
```

Expected: immutable install passes (lockfile is settled); tsc shows exactly the 2 known `motto` errors; build exits 0.

- [ ] **Step 7: Commit and push the client branch**

```bash
git add .yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch yarn.lock
git commit -m "$(cat <<'EOF'
fix: unblock trailing re-engage after formation turnarounds

Verified frame-by-frame from the 2026-08-28 beta clip: after a mid-walk
turnaround of a formed pair, the one-tile trailing acquire never ran -
the late JOINER paced the MASTER natively at a ~0.85-tile overlap for
~14 tiles with no freeze, no snap, no correction. Two gates caused it:

1. Re-engagement hysteresis: the turnaround releases the standing
   session (correct), arming the same-pair ENGAGE block. Its escape,
   sawSeparated, needs a >=1-tile Chebyshev observation - structurally
   impossible for a pair that is FORMING UP - so the full 3000ms
   backstop always elapsed, consuming the entire acquire window.
   Fix: record the released session's last confirmed shared direction
   (lockedDirX/Y) on _pixelrpLastReleased; while blocked-and-close, a
   samePathWith re-proof in a DIFFERENT direction (a turnaround
   re-forming the pair - a crossing/overtake loop keeps the SAME
   direction, so that protection is untouched) now counts as
   separation-grade proof and unblocks the same frame. New one-shot
   [sync:REENGAGE_UNBLOCKED] diagnostic. NaN direction keeps blocking.

2. Engage proximity gate: samePathWith's strict <1-tile Chebyshev made
   a pair whose native gap had already reached a full tile (server
   walk-grid slew finishing the formation while no session existed)
   permanently unengageable. Now <= 1 + 1e-6, matching the maintenance
   pathOk bound EXACTLY (a wider bound would engage pairs maintenance
   rejects and thrash engage->release). At exactly 1.0 the lateEntry
   acquire computes requiredTravel ~0 and spacing-locks instantly.

Not touched: acquire math, formation classifier, trailing correction,
persistentTrailingCompatible, server code, the 500-vs-530 unwrap
modulus, all existing [sync:*] diagnostics.

Verified: tsc --noEmit (only the 2 pre-existing motto errors), vite
build clean, patch reverse/forward-applied against a pristine tree with
zero rejects (byte-identical to node_modules), per-file hunk comparison
shows only RoomSpriteCanvas.ts changed, yarn install --immutable passes.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
git push -u origin feat/pathfinder
```

Expected: commit created on client `feat/pathfinder`; push succeeds. Record the commit SHA for Task 3.

---

### Task 3: CHANGELOG, submodule bump, and PR to beta

**Files:**
- Modify: `CHANGELOG.md` (plus repo root)
- Modify: `client` (submodule pointer → Task 2's SHA)

**Interfaces:**
- Consumes: the pushed client `feat/pathfinder` SHA from Task 2 Step 7.
- Produces: plus `feat/pathfinder` branch pushed with a PR open against `beta`; in-game verification handed to the user.

- [ ] **Step 1: Add the CHANGELOG entry**

In `/Users/rybealey/Documents/Personal/pixelrp/plus/CHANGELOG.md`, insert directly ABOVE the line `## 2026-08-27 — VIP membership arrives` (keeping one blank line before it):

```markdown
## 2026-08-27 — Walking in step

### Fixed

- **Falling into line behind someone works again after turning around.**
  When two people walking in single file turned around mid-walk, the one
  now behind could shuffle along awkwardly overlapping their partner for
  several seconds instead of settling neatly one tile back. Turning
  around now re-forms the line right away, and a pair that had already
  drifted into place locks in cleanly instead of never quite snapping.

```

(Player-facing wording, plain hyphens in the body, matching the file's house style. The `—` in the dated heading matches the existing headings.)

- [ ] **Step 2: Commit the bump + changelog on plus feat/pathfinder**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git checkout feat/pathfinder
git -C client rev-parse --short HEAD   # confirm this is Task 2's commit
git add client CHANGELOG.md
git commit -m "$(cat <<'EOF'
fix: trailing re-engage unblock after turnarounds (bump client)

Bumps the client to the RoomSpriteCanvas fix that restores the one-tile
trailing acquire after formation turnarounds: direction-aware unblock of
the re-engagement hysteresis, plus the engage proximity gate widened to
admit exactly-one-tile pairs (matching the maintenance bound). Spec:
docs/superpowers/specs/2026-08-27-trailing-reengage-unblock-design.md

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
git push -u origin feat/pathfinder
```

Expected: commit contains exactly `client` and `CHANGELOG.md`; push succeeds. (The spec and this plan are already committed on this branch.)

- [ ] **Step 3: Open the PR against beta**

```bash
gh pr create --base beta --head feat/pathfinder \
  --title "fix: restore one-tile trailing acquire after formation turnarounds" \
  --body "$(cat <<'EOF'
## Problem

Frame-by-frame analysis of twvst's 2026-08-28 turnaround clip showed the one-tile trailing acquire never engaging after a formed pair reverses mid-walk: the late JOINER paced the MASTER natively at a ~0.85-tile overlap for ~14 tiles. Root cause is two gates in the master/joiner sync, not the acquire math:

1. **Re-engagement hysteresis** - the turnaround release arms the same-pair ENGAGE block, whose escape (`sawSeparated`) requires a >=1-tile observation that a *forming* pair can never produce, so the 3000ms backstop always ran in full - consuming the entire acquire window.
2. **Engage proximity gate** - `samePathWith`'s strict `<1` tile makes a pair that natively finished forming (server walk-grid slew) permanently unengageable afterwards.

## Fix (client renderer patch only)

- Record the released session's last confirmed shared direction on `_pixelrpLastReleased`; a blocked-but-close pair that re-proves a shared route in a **different** direction (turnaround) unblocks the same frame. Same-direction re-proof (the crossing/overtake loop the hysteresis was built for) stays blocked - that protection is untouched. New `[sync:REENGAGE_UNBLOCKED]` diagnostic.
- Engage gate widened from `<1` to `<= 1 + 1e-6`, matching the maintenance `pathOk` bound exactly; at 1.0 the lateEntry acquire spacing-locks instantly with zero hold.

Untouched: acquire math, classifier, trailing correction, `persistentTrailingCompatible`, server code, the 500-vs-530 unwrap question, all existing diagnostics.

Spec: `docs/superpowers/specs/2026-08-27-trailing-reengage-unblock-design.md`

## Verification

- tsc --noEmit: only the 2 pre-existing `motto` errors; vite build clean
- Patch reverse/forward-applies against a pristine tree with zero rejects, byte-identical to node_modules; per-file hunk comparison shows only `RoomSpriteCanvas.ts` changed; `yarn install --immutable` passes
- In-game (beta, pending): turnaround of a formed pair should log `RELEASE_REASON -> REENGAGE_UNBLOCKED (direction_change) -> ENGAGE lateEntry=true -> TRAIL_LATCH/TRAIL_LOCK` and settle exactly one tile behind within ~1.5 tiles. Regression: plain crossings/overtakes stay fully native, `REENGAGE_BLOCKED` still fires for same-direction re-proof inside 3s.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 4: Hand off for in-game verification (do not merge)**

Report to the user, including:
- The PR URL, and that merging to beta (auto-deploy) is their call.
- Test script: two accounts in one room; walk in single file until the one-tile formation forms; turn around mid-walk (click a tile behind you); watch the follower.
  - Expected: follower settles exactly one tile behind within ~1.5 tiles of the leader's travel; console shows `[sync:RELEASE_REASON]` → `[sync:REENGAGE_UNBLOCKED] reason=direction_change` → `[sync:ENGAGE] ... lateEntry=true` → `[sync:TRAIL_LATCH]`/`TRAIL_LOCK`.
  - Also test: start stacked on one tile and walk (the original stacked-departure case still works — freeze ≤ ~530ms then exact spacing); an already-formed pair walking in from the start gets captured and spacing-locked (`[sync:ENGAGE]` at planar gap ~1.0, no hold).
  - Regression: walk two avatars *through* each other (crossing) and overtake — both must render fully native, no magnet feel; a same-direction re-engage inside 3s still logs `[sync:REENGAGE_BLOCKED]`.

---

## Self-Review (completed)

- **Spec coverage:** Change 1 → Task 1 Steps 2-4; Change 2 → Task 1 Step 5; verification ritual → Task 1 Steps 6-7 + Task 2 Steps 3-6; CHANGELOG → Task 3 Step 1; branch/PR mechanics → Task 1 Step 1, Task 2 Step 7, Task 3 Steps 2-3; in-game expectations → Task 3 Step 4. No gaps.
- **Placeholder scan:** all steps carry exact code, commands, and expected outputs; no TBDs.
- **Type consistency:** `_pixelrpLastReleased` gains `dirX/dirY` in Edit A (type) and Edit B (sole construction site); Edit C reads the same names. `sharedDirX/sharedDirY` are local to Edit C. Gate bound `(1 + 1e-6)` matches the existing maintenance literal.
