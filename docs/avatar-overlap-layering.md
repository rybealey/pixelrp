# Avatar Overlap & Layering: Investigation and Fixes

**Status:** Resolved and deployed to production. Verified live by multi-player walk-through testing.

This document covers the full arc of the "players flicker/overlap when sharing or crossing tiles" issue: what the symptoms actually were (three distinct bugs plus a timing artifact, all presenting as "overlap looks wrong"), what we discovered about the Nitro renderer's depth sorting, every fix attempted (including the ones that didn't work and why), and the final implementation that resolved it.

---

## 1. The symptoms

What was reported over several sessions, in order:

1. **Same-tile flicker** — two players standing on (or walking onto) the same tile rapidly swapped which one rendered in front, frame after frame.
2. **Walking flicker** — a player walking through or past another player flickered in front/behind mid-step, even when they never actually shared a tile at rest.
3. **Half-tile formation offset** — a player following another on the same path rendered a *fraction* of a tile behind (e.g. 0.5 tiles) instead of exactly N whole tiles behind, making the pair look like they were overlapping/clipping while co-walking.
4. **Stalls** — walking sometimes hitched or froze briefly. This turned out to be unrelated to layering entirely (see §6).

These were tangled together in testing because they co-occur: co-walking players both flicker *and* sit at fractional offsets, and a transport stall makes any of it look worse.

---

## 2. Background: how the Nitro renderer sorts depth

All findings are against `@nitrots/nitro-renderer@1.6.6`, `src/room/renderer/RoomSpriteCanvas.ts` (maintained as a Yarn patch in `client/`).

Key mechanics discovered during investigation:

- Every visible sprite becomes a `SortableSprite` each frame, sorted by a single scalar depth: `z + sprite.relativeDepth + tiny biases`, sorted descending (`(a, b) => b.z - a.z`), so **smaller z renders on top**.
- A room unit's base `z` is **quantized to its rounded tile** via `RoomObjectLocationCacheItem` — not its true interpolated position. While walking, the unit's depth does not glide; it **jumps by a full tile quantum at the lerp midpoint** of each step.
- Consequence: two units walking near each other are almost never at "close" z mid-step. Each unit's rounding flips at *its own* midpoint, so during large windows of every step the pair's quantized depths sit **a full tile quantum apart**, in an order that flips every step. Any comparator condition of the form "if their z values are close, apply special handling" is structurally defeated by this — the special handling disengages exactly when it's needed.
- Vanilla tie-breaking for exactly-equal depths adds `|screenX| * 1.2e-7`. Screen X **changes every frame while walking**, so two units tied at the same base depth (same tile, or the same isometric depth row — diagonals tie too) swap order continuously. This is the raw mechanism of the standing-still flicker.
- A second vanilla bias, `3.7e-11 * count` (sprite emission order), is also frame-unstable: emission order depends on iteration order of the object map, which changes as objects enter/leave.
- The local player's body sprite gets a `-0.001` depth adjust (`AVATAR_OWN`), the engine's own "your avatar wins ties" mechanism — but it only helps when depths are within 0.001, which the tile-quantum jumps blow straight past.
- `relativeDepth` separates a unit's own sprite stack: body/effect overlays/bubbles sit below ~0.5, while the **shadow decal sits at relativeDepth 1** — this became the discriminator for keeping shadows under everything.

### External diagnosis, refuted

Mid-investigation an external AI-generated analysis prescribed three emulator-side fixes (stabilizing server Z updates, reordering status serialization, changing the movement update cadence). All three were checked against the actual codebase and refuted: the server was already emitting stable, correct positions; the flicker reproduced with a *stationary* pair (no movement packets at all); and the instability was demonstrably client-side in the per-frame sort. This confirmed the fix belonged in `RoomSpriteCanvas.ts`, not the emulator.

---

## 3. The fixes, in order

### Fix 1 — Stable per-object bias for units (shipped, kept)

**Problem:** exact-depth ties broken by frame-varying terms (`|screenX|`, emission count).

**Fix:** units (`user`, `pet`, `bot`, `rentable_bot`, `monsterplant` — `UNIT_TYPE_KEYS`) get a **static** per-object bias instead:

```ts
z = (z + ((object.instanceId % 199) * 2E-6));
```

Max ~4e-4, deliberately below the 0.001 granularity of intentional layer offsets, so the own-avatar `-0.001` adjust still wins every tie in the player's own view. The same pair now always stacks the same way.

**Result:** fixed the *standing-still* same-tile flicker. Walking flicker persisted.

### Fix 2 — Units skip the screen-x tie-break term (shipped, kept)

**Problem:** even with the static bias, units tied on the same isometric depth **row** (diagonal neighbours tie at identical base depth!) still carried the per-frame `|screenX| * 1.2e-7` term, which dominated the static bias and flipped tied pairs while either walked.

**Fix:** the screen-x term is skipped entirely for unit-type objects; non-units keep vanilla behaviour.

**Result:** eliminated the diagonal-row flip. Walking-through-each-other flicker *still* persisted.

### Fix 3 — POV comparator keyed on z-closeness (shipped, then superseded)

**Hypothesis:** make `AVATAR_OWN` an explicit comparator-level tie-breaker — when two units' depths are close, force the own avatar's stack above the other's.

**Why it failed:** the tile-quantization discovery in §2. Mid-step, the pair's quantized depths transit windows a **full tile quantum apart**, so no "close z" threshold both (a) engages during the step and (b) stays sane for genuinely distant units. The order followed the transient z and flipped every step. This failure is what produced the key insight.

### Fix 4 — Coordinate-based overlap rule (shipped, FINAL — this is the fix)

**The key insight:** *overlap is a property of positions, not depths.* Whether two avatars are on/entering/crossing the same tile is answerable exactly from their **raw room coordinates** (the lerped tile positions, which move smoothly), and must **ignore z entirely** — z is the corrupted signal, so no form of it can be in the trigger condition.

**Implementation** (all in `RoomSpriteCanvas.ts`):

Every sprite of a unit is stamped with its owner's grouping identity at emission time:

```ts
// own via object.model.getValue<number>('own_user') > 0  (RoomObjectVariable.OWN_USER)
// tx/ty from object.getLocation() — the RAW lerped room position, NOT the quantized depth tile
(sortableSprite as any).__pixelrpUnit = { id, own, tx, ty };
```

The sort comparator then applies an atomic-stack override:

```ts
this._sortableSprites.sort((a, b) =>
{
    const aUnit = (a as any).__pixelrpUnit;
    const bUnit = (b as any).__pixelrpUnit;

    if(aUnit && bUnit && (aUnit.id !== bUnit.id)
        && (Math.abs(aUnit.tx - bUnit.tx) < 1)
        && (Math.abs(aUnit.ty - bUnit.ty) < 1)
        && a.sprite && (a.sprite.relativeDepth < 0.5)
        && b.sprite && (b.sprite.relativeDepth < 0.5))
    {
        if(aUnit.own !== bUnit.own) return (aUnit.own ? 1 : -1);

        return (bUnit.id - aUnit.id);
    }

    return (b.z - a.z);
});
```

Reading the rule:

- **Trigger:** two *different* units whose raw positions are within one tile on **both** axes — sharing a tile, or moving onto/through each other's tile. Pure geometry; z never consulted.
- **Effect:** each unit's above-ground stack (body + effect overlays + bubbles, `relativeDepth < 0.5`) is ordered **as one atomic layer**: the local player's stack always wins; between two other players, higher instance id sits behind (consistent with the Fix-1 numeric bias, so the engaged and disengaged states agree).
- **Shadows excluded:** `relativeDepth >= 0.5` sprites (the shadow decal at 1) fall through to the numeric sort so shadows stay under every body.
- **Everything else** — furniture, walls, one unit's internal stack — keeps the plain numeric `b.z - a.z` sort.

**Result:** user-confirmed fixed ("This finally fucking worked"), and it has held through subsequent live testing.

---

## 4. The formation-offset problem (server-side timing)

With layering solved, the remaining visual overlap was **temporal**: a follower on the same path rendered a constant *fraction* of a tile behind the leader, so their sprites partially overlapped while co-walking.

**Root cause:** the walk-responsiveness pass gave each walker a private 500ms metronome (`SelfPaceWalk`, in `emulator/HabboHotel/Rooms/RoomUserManager.cs`) anchored to their own first step. Two walkers therefore stepped with an arbitrary 0–500ms phase offset between them; the client lerps each step over its animation window, so a constant phase offset renders as a constant fractional-tile spatial offset.

**Fixes (both in `RoomUserManager.cs`):**

1. **Shared-grid phase lock:** every walker's beats converge onto a single wall-clock 500ms grid (multiples of `BeatMs` on `Environment.TickCount64`) by **lengthening** beats only, at most `SlewMaxMs = 30` ms per beat:

   ```csharp
   var toGrid = (int)((BeatMs - (next % BeatMs)) % BeatMs);
   next += Math.Min(SlewMaxMs, toGrid);
   ```

   Lengthen-only preserves the 1 tile / 500ms speed cap; 30ms stays inside the client's per-tile animation window so converging steps don't stutter. The first beat is exempt (the instant first step's follow-up must come 500ms after it, wherever the grid sits). All walkers end up stepping at the same instants → whole-tile offsets.

2. **Grid-locked formation joins:** the edge case where the slew was still converging — a player *starting* a walk right next to (Chebyshev distance ≤ 2) an already-walking player skips the instant first step and waits for the shared grid (≤500ms), so the pair is phase-locked from step one. Solo starts keep the instant first step.

3. **Client window widened 515ms → 530ms** (`MovingObjectLogic.DEFAULT_UPDATE_INTERVAL` in the renderer patch) to absorb the ≤30ms slewed beats without mid-step animation stutter.

Supporting machinery: `user.WalkGeneration` supersession tokens ensure a newer pace loop cleanly kills any pending older one (no double-steps), and everything serializes against the room tick via `_cycleLock`.

---

## 5. Invariants — do not regress

- **The overlap trigger keys on ROOM COORDINATES, never z.** Any future "improvement" that reintroduces a z-closeness condition to the comparator will reintroduce the walking flicker, because mid-step quantized depths transit full-tile-quantum windows. This is the load-bearing property of the entire fix.
- `tx`/`ty` must come from `object.getLocation()` (raw lerped position), not from the depth tile.
- Units must keep the static `instanceId % 199` bias and must **not** get the `|screenX|` term back.
- The atomic-stack override must keep excluding `relativeDepth >= 0.5` (shadows are ground decals).
- The disengaged tie-break (`bUnit.id - aUnit.id`) must stay consistent with the numeric id bias so engaging/disengaging the rule doesn't itself cause a swap.
- Server-side: grid slew must remain **lengthen-only** (speed cap) and ≤30ms/beat (client window); beat-1 exemption must stay.
- The comparator lives in the **Yarn patch** on `@nitrots/nitro-renderer@1.6.6` — reseal via the full 12-file patch flow; verify marker `aUnit.tx - bUnit.tx` survives any reseal.

## 6. Related but separate: the stalls

Walk stalls observed during this saga were **not** a layering or pacing bug. TEMP `[gap]` telemetry in the production client (still present, `__pixelrpMoveGaps`) proved movement packets leave the server on a clean ~500ms cadence but arrive **bunched** through Cloudflare's proxying of the game socket (`wss://pixelrp.co:2096`) — patterns like `1580ms → 0ms → 13ms`. The fix is a pinned infrastructure task (grey-clouded `ws.pixelrp.co` + Let's Encrypt cert + host nginx block, runbook ready); the `[gap]` logger stays until the before/after verdict.

## 7. File reference

| File | Role |
|---|---|
| `client/node_modules/@nitrots/nitro-renderer/src/room/renderer/RoomSpriteCanvas.ts` (Yarn patch) | Static unit bias, screen-x skip, `__pixelrpUnit` stamping, coordinate-overlap comparator |
| `client/node_modules/@nitrots/nitro-renderer/src/room/object/logic/MovingObjectLogic.ts` (Yarn patch) | 530ms per-tile window; TEMP `[gap]` logger |
| `emulator/HabboHotel/Rooms/RoomUserManager.cs` | `TryInstantFirstStep` (cooldown scheduling + formation-join grid lock), `SelfPaceWalk` (metronome + shared-grid slew), `WalkGeneration` supersession |
| `emulator/HabboHotel/Rooms/RoomUser.cs` | `WalkGeneration` field |
