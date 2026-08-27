# Trailing Re-engage Unblock — Design Spec

**Date:** 2026-08-27
**Branch:** `feat/pathfinder` (client submodule branch `feat/pathfinder` off `pixelrp` @ `8fa809b3`)
**File touched:** `client` yarn patch — `node_modules/@nitrots/nitro-renderer/src/room/renderer/RoomSpriteCanvas.ts`, resealed into `.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch`

## Problem

Verified frame-by-frame against twvst's 2026-08-28 beta clip (two avatars in formation
performing a mid-walk turnaround): the one-tile trailing acquire system never engaged.
The JOINER paced the MASTER natively at a ~0.85-tile gap for ~14 tiles with no freeze,
no snap, and no correction. Two gates in the master/joiner sync lock the system out:

1. **Re-engagement hysteresis** (`_pixelrpLastReleased`, eval ~lines 1038–1048 of the
   patched file). A turnaround releases the standing session (genuine divergence —
   correct), which arms a block on fresh ENGAGE for the same pair. The escape,
   `sawSeparated`, requires observing Chebyshev distance ≥ 1 tile — structurally
   unsatisfiable for a pair that is *forming up* (they sit under 1 tile apart by
   definition until acquisition completes). The 3000ms backstop therefore always runs
   in full, consuming the entire window in which the acquire could have acted.
2. **Engage proximity gate** (`samePathWith`, ~line 1004): strict `< 1` tile on both
   axes. Once the native gap reaches a full tile (the server's ≤30ms/beat grid slew
   finishes the job natively during the blocked window), the pair becomes permanently
   unengageable — no lock, no future correction.

Every release re-arms a fresh 3000ms block, so patrol-style movement (bot
Walk Horizontally/Vertically, staff `:walk`) hits this on every reversal.

## Fix (two surgical changes, client-only)

### Change 1 — direction-aware unblock of the hysteresis

- Extend `_pixelrpLastReleased` with `dirX`/`dirY`: the released session's last
  confirmed shared direction, captured from `sync.lockedDirX/Y` at the existing record
  site (~line 2157). `NaN` if the session never confirmed a direction.
- In the hysteresis evaluation, where today only `!stillClose` can set `sawSeparated`:
  when the pair is still close BUT currently re-proves a shared route
  (`samePathWith(own)` matches) whose shared direction **differs** from the stored
  release direction, set `sawSeparated = true`. A turnaround is a new route
  relationship, not the old crossing continuing. `recentlyReleasedBlocked` is computed
  immediately after, so ENGAGE proceeds the same frame.
- If the stored direction is `NaN`, keep blocking (conservative — matches today).
- New one-shot diagnostic: `[sync:REENGAGE_UNBLOCKED] reason=direction_change` with
  pairKey, stored dir, new dir, sinceReleaseMs.
- The Chebyshev separation test and the 3000ms backstop stay untouched for
  same-direction cases — the crossing/overtake release-loop protection this hysteresis
  was built for (commit `948b1c08`) is fully preserved.

### Change 2 — admit exactly-one-tile pairs at the engage gate

- `samePathWith`'s proximity gate changes from `< 1` to `<= 1 + 1e-6` on both axes —
  the *same* bound the maintenance path (`pathOk`, ~line 1396) already deliberately
  uses. Engage and maintenance bounds must stay identical: any wider engage epsilon
  admits pairs that maintenance then rejects, producing engage→release thrash that
  re-arms the hysteresis.
- No other code needed: at an exactly-1.0 engage, `lateEntryAtEngage` fires (planar
  gap > `FORMATION_STACKED_PLANAR_GAP_MAX` 0.10) → TRAILING + acquire →
  `trailingAcquireRequiredTravel ≈ 0` → the hold is skipped and
  `trailingSpacingLocked` latches immediately — instant crisp lock, zero freeze.
- Packet-jitter frames reading 1.0 ± 0.04 are harmless: engage needs one ≤ 1.0 frame;
  `badSince` (120ms) and the trailing grace (150ms) absorb the flicker afterwards.

### Explicitly untouched

Acquire math, formation classifier, trailing correction pipeline,
`persistentTrailingCompatible`, all emulator/server code, the phase-unwrap 500-vs-530
modulus question, the `[sync:*]` TEMP DEBUG logs (they are the verification
instrument for this fix), and the `[gap]` logger (separate pending work).

## Expected behavior (the clip's scenario, post-fix)

Turnaround → release (unchanged) → block lifted the moment the pair re-proves the
route in the reversed direction (~0.3s later, when the late side's first reversed
step is mid-flight) → ENGAGE with `lateEntry=true` at gap ~0.6–0.8 → acquire hold
~100–240ms → exact one-tile lock within ~1.3 tiles of master travel (budget: <1.5).

## Verification

Build ritual (per twvst's convention and the reseal trap):
1. `tsc --noEmit` clean, vite build clean.
2. Reseal the yarn patch — `yarn install` BEFORE resealing; verify per-file patch
   content against the prior patch (only `RoomSpriteCanvas.ts` hunks change).
3. Patch reverse/forward-applies against a pristine tree with zero rejects;
   `yarn install --immutable` passes (update the yarn.lock resolution hash if the
   patch content hash changes).

In-game (manual, handed off): reproduce the clip — two avatars walk in formation,
turn around mid-walk. Expected console sequence:
`[sync:RELEASE_REASON]` → `[sync:REENGAGE_UNBLOCKED] reason=direction_change` →
`[sync:ENGAGE] lateEntry=true` → `[sync:TRAIL_LATCH]` / `TRAIL_LOCK`, with the joiner
locked one tile behind within ~1.5 tiles. Regression check: two avatars crossing /
overtaking still render fully native — no magnet feel, no re-engage loop
(`[sync:REENGAGE_BLOCKED]` still fires for same-direction re-proof inside 3s).

CHANGELOG.md entry (player-facing movement fix).

## Risks / residuals

- Same-direction restart within 3s of a release remains blocked up to the backstop —
  acceptable residual; self-heals at 3s, and Change 2 makes post-slew capture possible
  so the pair still ends cleanly locked.
- A 90° corner "turnaround" also unblocks (direction differs) — desirable: it is a
  genuinely new formation geometry.
- Client-only change; no wire, server, or DB impact.
