# Redirect boundary race — the joiner/crossing hitch

**Date:** 2026-09-22
**Status:** Proposed — not implemented, no code changed

## Summary

A redirect that is decided very close to the boundary of the edge it restages
rewrites geometry the client has *already begun rendering from lookahead*. The
avatar visibly snaps. Measured on beta, not inferred: `minRedirectMarginMs=2`,
with 51 redirects landing inside 50ms.

The proposed fix is to plan such a redirect from `e + 2` instead of `e + 1`,
costing up to one beat of turn latency on ~3% of redirects.

## Evidence

`:movementstats`, Harvey Milk Medical Center, 2026-09-22 22:11, one unit in
room, 4392 frames handed off:

```
starts=596 redirects=1546 advances=9451 commits=9451
redirectMarginUnder250=418 under100=132 under50=51 minRedirectMarginMs=2
correctionEPlus1ImmediateStaged=1523 correctionEPlus1NotFuture=0
correctionEPlus1AlreadyStaged=0 correctionEPlus1Escort=23
redirectDeferredBehindElapsing=2 redirectDeferredRecovered=2
beatsLate=0 maxBeatLatenessMs=0 schedulerFaults=0 spinGuards=0 roomFaults=0
pathfind=2189 partial=136 failed=14
```

The server side is clean. `advances == commits` exactly, no late beats, no
faults, no spins, no orphans, q1 depth 0. Nothing here supports a server-side
cause.

What does stand out is the margin distribution: 27% of redirects land within
250ms of the boundary, 8.5% within 100ms, 3.3% within 50ms, and the closest
observed was 2ms.

## Mechanism

`PublishCorrectedEdgeEarly` exists precisely because the boundary record for
`e + 1` arrives too late: the client starts rendering `e + 1` from lookahead
the instant its `cycleStart` passes, without waiting for a packet. Publishing
the corrected geometry as soon as the redirect decides it wins that race —
*when there is enough margin left to win it*.

At a 2ms margin there is not. The packet is still in flight when the client
begins the edge, so the corrected geometry lands on an edge already at a live
phase and the drawn path changes underneath it.

This is the case the counters were added to size, and the comment on them
already records a sighting: edge 103 turning from `8,16->8,17` into
`8,16->7,15` at phase 0.128 — 64ms into a 500ms edge, which is about one
network trip.

### Why the existing guard does not catch it

`PublishCorrectedEdgeEarly` re-reads the clock and bails when
`w.ElapsingEdgeIndex(now) >= index`, counting `CorrectionEPlus1NotFuture`.

That counter is **0**. The guard is not broken; it answers a different
question. It asks whether the edge has started *on the server*. With 2ms to
go the honest answer is "not yet", so it publishes. It never asks whether the
packet can arrive before the *client* starts drawing that edge — and below one
round trip of margin, it cannot.

The guard is a correctness check against rewriting an elapsed index. The race
described here is a separate, unguarded condition.

## Why it is hard to reproduce

The fault requires clicking a new destination inside a narrow window before a
500ms boundary. At a 50ms threshold that is roughly a 1-in-10 chance per
direction change, and it also depends on the player's latency at that moment.
Deliberate reproduction means hitting a ~50ms window on purpose; normal play
hits it several times an hour without ever being able to repeat it on demand.

## Proposed change

When the margin to `e + 1`'s boundary is below a safety threshold, plan the
redirect from `e + 2` instead.

- The client's lookahead for `e + 1` stays valid, so no geometry changes under
  a live phase.
- `e + 2` is corrected with a full beat of lead time, comfortably ahead of any
  plausible round trip.
- The threshold should be a named constant in `MovementSettings`, tunable
  without touching the controller.

### Cost

On redirects that fall inside the threshold, the new direction takes effect one
beat later — up to 500ms. At a 50ms threshold that is ~3% of redirects; at
100ms, ~8.5%. Everything above the threshold is unaffected.

The trade is latency on a small minority of turns against a visible snap.

### What must not change

Anything the `PublishCorrectedEdgeEarly` comment already lists as untouched:
`TimelineOrigin`, `WalkSessionId`, the `RouteRevision` rules, the 500ms
interval, `EmittedThroughEdge`'s meaning, the lookahead policy and the packet
format. This is a change to *which index* a near-boundary redirect plans from,
and nothing else.

## Open questions

1. **Threshold value.** 50ms is the smallest bucket already counted, not a
   measured round trip. The honest version measures actual RTT before picking a
   number; the pragmatic version starts at one interval's worth of headroom and
   tunes from the counters.
2. **Escorts.** `CorrectionEPlus1Escort=23` — escorted walkers already skip
   early publication to keep captor and shadow in lockstep. Whether they need
   the same deferral, or are protected by taking the normal path, is not
   established here.
3. **`partial=136 / failed=14`** out of 2189 pathfinds (6% partial). Unrelated
   to this race, but unexplained and worth its own look.

## Not investigated

- **Client clock rebase.** `updateClock` reassigns the offset in one step when
  a sample is more than 5000ms out, rather than easing at the usual 4ms cap.
  Mid-walk that shifts every drawn position at once. It has no counter and no
  log, so there is no evidence either way — it is simply unmeasured. Adding a
  counter is a client-side change.
- **Stale drop.** `STALE_MS=1400` deletes the unit and returns the avatar to
  native prediction. Counted as `staleDrops` client-side, but without a
  timestamp it cannot be lined up against a sighting.
