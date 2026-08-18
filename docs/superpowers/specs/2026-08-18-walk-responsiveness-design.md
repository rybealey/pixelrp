# Walk Responsiveness & Smoothness Pass — Design

**Date:** 2026-08-18
**Status:** Approved
**Scope:** PlusEMU emulator (`emulator/`, branch `pixelrp`) + nitro-renderer yarn patch (`client/`, branch `pixelrp`)

## Problem

Players feel three timing defects when walking:

1. **Pause before moving** — a click from standing takes a perceptible beat
   (~150–300ms real, reads as 300–500ms) before the avatar starts.
2. **Stutter while walking** — the avatar micro-pauses at each tile boundary
   during multi-tile walks.
3. **Sluggish redirects** — clicking a new tile mid-walk takes up to a full
   beat to change course.

### Assessment findings (what was measured in code)

The pixelrp **instant-first-step** (`TryInstantFirstStep` + `SelfPaceWalk`,
commit `84aee5ff`) is deployed and enabled on prod (no
`pathfinder.instant.first.step.disabled` row in `server_settings`; missing key
reads as "0" = enabled). The server emits the first step immediately. The
residual delay/stutter comes from a stack of smaller sources:

- **Nagle's algorithm is on.** `WebsocketGameServer` (NetCoreServer) never
  sets `OptionNoDelay`, so the kernel may batch the small per-step `"mv"`
  status packets — latency *and* jitter on every packet in the game.
- **Beat cadence drifts late.** `SelfPaceWalk` waits `Task.Delay(500)` *after*
  each beat's processing, so per-step lateness (processing + timer slop)
  accumulates. The global room tick fires at 500–525ms (500ms threshold polled
  on a 25ms sleep in `Game.GameCycle`).
- **The client animates each tile over exactly 500ms**
  (`MovingObjectLogic.DEFAULT_UPDATE_INTERVAL`). Any step packet arriving
  later than 500ms after the previous one leaves the avatar frozen at the
  tile edge for the slack — the visible stutter.
- **Instant-step cooldown hole.** A standing click landing inside the 450ms
  instant-step rate cap silently falls back to the drifting global tick
  (worst case ~525ms) instead of being scheduled.
- Click-on-mouseup press time (~80ms) and the client's 24fps frame (~20ms avg)
  are fixed perceptual costs; mousedown-walking is off the table because
  mousedown must stay free for camera dragging.

Redirect semantics are already optimal for tile-locked movement (the new goal
is recalculated on the same beat that commits the in-flight tile); redirects
only *feel* sluggish because the beat itself drifts late.

## Design

Five components, independent, shipped as one deploy.

### 1. Socket NoDelay — `Communication/Abstractions/WebsocketGameServer.cs`

Set `OptionNoDelay = true` in the constructor so accepted sessions disable
Nagle. Unconditional (standard for real-time games); no config switch.

### 2. Metronome self-pacing — `RoomUserManager.SelfPaceWalk`

Replace delay-after-processing with absolute scheduling on a monotonic clock
(`Stopwatch`): beat *n* is due at `t₀ + n×500ms`, where `t₀` is when the
instant first step was emitted. Each iteration sleeps `due − now` (floor at
1ms). Processing time and timer slop no longer accumulate; steps arrive
metronome-even, which the client's fixed 500ms tile animation depends on.
All existing guards are unchanged: `_cycleLock` serialization, `IsValid`,
stop-on-arrival/leave, `SelfPaced` handshake with the global tick, kill
switch.

### 3. Tighter global tick — `Game._cycleSleepTime` 25 → 5

Average tick lateness drops ~12.5ms → ~2.5ms; bots and any tick-paced
movement smooth out identically. **Condition:** verify
`ClientManager.OnCycle` is internally time-gated (or gate it) so the 5×
poll rate doesn't multiply unrelated per-loop work.

### 4. Cooldown-hole scheduling — `RoomUserManager.TryInstantFirstStep`

When a standing click lands inside the 450ms rate cap: instead of returning
(leaving `PathRecalcNeeded` for the global tick), mark the user `SelfPaced`
immediately and start the self-pace loop with a **first-beat delay** of
`(lastInstantStep + 500ms) − now`. The loop gains an optional first-delay
parameter and, for that first beat only, processes the user even though
`IsWalking` is still false (the pending `PathRecalcNeeded` pathfinds and
emits the first step). Marking `SelfPaced` up front keeps the global tick
from double-processing. Walk speed remains capped at one tile per 500ms —
this fixes consistency, not speed. The existing kill switch disables this
along with the instant step (full fallback to today's tick behavior).

### 5. Client glide — renderer yarn patch, `MovingObjectLogic.ts`

`DEFAULT_UPDATE_INTERVAL` 500 → **515**. The per-tile animation slightly
outlasts the server beat, so residual network jitter lands inside the
animation window instead of freezing the avatar at the tile edge. The lerp
restarts from the avatar's current rendered position on every update, so the
~15ms lag never accumulates; arrival completes ~15ms later (imperceptible).
Rollers inherit the same smoothing. Implemented as a new hunk in the existing
`@nitrots/nitro-renderer` patch — **full reseal with all 7 files verified
present** before `patch-commit` (established patch discipline).

## Error handling

No new failure modes. The self-pace loop keeps its try/catch with `SelfPaced`
reset; scheduling reuses the loop's existing exit guards. Components 1/3/5
are constants. Kill switch `pathfinder.instant.first.step.disabled = 1`
restores today's tick-driven behavior for 2 and 4.

## Testing & verification

- Emulator: `dotnet build` clean; extract the beat-due computation into a
  pure helper if it lets a unit test cover the schedule math cheaply.
- Verify `ClientManager.OnCycle` gating before tightening the loop (comp. 3).
- Client: rebuild via `build-client.sh`; verify the resealed patch applies
  cleanly on `yarn install`.
- Feel test: user tests locally in-game (standing click, long walk, rapid
  redirects, rapid single-tile hops), then prod deploy and re-test.
- CHANGELOG: player-facing entry ("walking responds faster and glides more
  smoothly").

## Deferred (assessed, intentionally not built)

- **A\* correctness** — `PathFinder` bakes the heuristic into accumulated
  g-cost and uses squared distance (non-admissible); can zigzag. No player
  complaint today.
- **Hot-loop allocation hygiene** — per-step `ToList()` copies,
  per-call `PathFinderNode[X,Y]` grids. GC jitter fuel in busy rooms only.
- **Walk-on-mousedown** — conflicts with camera dragging; rejected.
