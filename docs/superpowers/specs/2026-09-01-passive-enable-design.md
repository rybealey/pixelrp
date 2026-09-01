# Passive Enable — design

**Date:** 2026-09-01
**Status:** Approved for planning

## Goal

Give every player currently in **passive state** an ambient avatar effect ("enable")
— the custom `Passive_Enable.nitro` bundle — and automatically remove it the moment
they leave passive for any reason.

## Background: how passive already works

- **Passive state** is `habbo.RpPassiveSeconds > 0`, a countdown of *online* seconds
  persisted in `user_rp_stats.passive_seconds`. `RpPassiveLastTick` is the transient
  decrement clock.
- **Entered** by: consuming a Passive Smoothie (`RpUseItemEvent.cs:60`, sets `3600`),
  or the RCON `give_user_passive` command (`GiveUserPassiveCommand.cs:38`), or loaded
  from DB on login (`Habbo.cs:243`).
- **Exited** by exactly two explicit paths:
  1. Countdown reaches 0 in the room tick (`RoomUserManager.cs:1260`).
  2. Player clicks the ✕ on their HUD passive tag (`RpPassiveCancelEvent.cs:20`).
  Logout drops it implicitly (effects are room-scoped visuals).
- **Safe zones** freeze the countdown but the player *remains passive* — the enable
  must stay on there.

## Background: how effects work

- Single slot: `habbo.Effects.CurrentEffect`. Apply/clear via
  `Effects.ApplyEffect(id)` — sets `CurrentEffect` and broadcasts `AvatarEffectComposer`
  to the room. `ApplyEffect(0)` and `ApplyEffect(-1)` both clear the visual
  (`-1` is the client "reset" value used when walking off effect tiles).
- The room tick already arbitrates the slot every cycle: horse riding re-asserts `77`
  (`RoomUserManager.cs:1316`), effect tiles/items via `UpdateUserEffect` (`:1951`),
  dances via `DanceComposer`. Applying any effect stops an active dance
  (`EffectsComponent.cs:95`).

## Behavior: "baseline that resumes"

The passive enable is the player's **underlying baseline** effect. Transient effects
(dance, ride, effect-tile, effect-item) temporarily take the slot; when they end, the
enable comes back on its own. Confirmed intent: *other effects and dances take place
while the passive enable stays intact and resumes afterward.*

## Design

### 1. Asset + effect id

- Effect ids currently run 1–247 with no gaps → claim **248**.
- Constant `PASSIVE_ENABLE_ID = 248` in the emulator.
- Place the bundle at `nitro/assets/bundled/effect/Squad.nitro` (internal lib `Squad`,
  kept as-is — invisible to players, avoids a repack).
- Add one entry to `nitro/assets/gamedata/EffectMap.json`:
  `{"id":"248","lib":"Squad","type":"fx"}`.
- No DB rows (effects don't use them). No client code change (client reads EffectMap).

### 2. Arbitration helper (per-tick safety net)

New helper `UpdatePassiveEffect(RoomUser user)`, called once per user per tick
immediately after `UpdateUserEffect(user, x, y)` (`RoomUserManager.cs:1322`). It only
calls `ApplyEffect` when the value actually changes (no per-tick broadcast spam):

```
passive = habbo.RpPassiveSeconds > 0
cur     = habbo.Effects.CurrentEffect

if passive:
    if (cur == 0 || cur == -1) && !user.IsDancing:
        ApplyEffect(PASSIVE_ENABLE_ID)      // slot free → assert baseline
    // else: a transient effect (or a dance) owns the slot → leave it.
    //       When it resets to 0/-1, the next tick re-applies 248.
else:
    if cur == PASSIVE_ENABLE_ID:
        ApplyEffect(0)                       // no longer passive → clear baseline
```

- The `!user.IsDancing` guard prevents killing a dance (any `ApplyEffect` stops the
  dance). Once `cur == 248`, starting a dance leaves `cur` untouched, so the dance plays
  and the enable stays the underlying effect.
- Walking off an effect tile sets `cur = -1`; the next tick re-asserts 248. A one-tick
  (~0.5s) flicker is possible here and matches existing tile-effect behavior.

### 3. Explicit apply/clear at lifecycle edges (no pop; tick is the safety net)

- **Enter passive via smoothie** — `RpUseItemEvent.cs:60`: after setting
  `RpPassiveSeconds = 3600`, apply 248 immediately for the room user.
- **Room entry while passive** — `RoomUserManager.cs` room-entry path (near the stats
  send at `:278`): if `RpPassiveSeconds > 0`, apply 248 immediately so there is no pop
  on room change. (This is also the path RCON grants get picked up when they next enter
  or on the next tick.)
- **Exit via ✕** — `RpPassiveCancelEvent.cs:20`: after zeroing passive, clear 248.
- **Exit via countdown** — `RoomUserManager.cs:1260`: after `RpPassiveSeconds` hits 0,
  clear 248.
- Guard every clear so it only clears when `CurrentEffect == 248` (never stomp a
  dance/tile/item effect the player happens to be showing at the moment passive ends;
  the next tick's `else` branch is a further safety net).

### 4. RCON grant path

`give_user_passive` sets passive without a guaranteed room context. No explicit apply is
added there; the per-tick helper applies 248 on the granted player's next cycle. Documented,
not a bug.

## Out of scope / YAGNI

- No persistence of the effect itself (it's derived from passive state, re-derived each
  session/room).
- No new packets, no client changes, no DB schema.
- Not renaming the internal lib `Squad` (optional future tidy).

## Verification

- Emulator builds.
- In-game (manual, per house style): drink a smoothie → enable appears; change rooms →
  still on; walk onto/off an effect tile → tile effect shows then enable resumes; dance →
  dance plays and enable persists/resumes; ride → 77 shows then enable resumes; click ✕ →
  enable gone; let countdown expire → enable gone; safe zone → enable stays.
- Whether the enable visually survives *during* a dance is a client-render question to
  confirm in-game.

## Deploy notes

- Emulator code changes deploy via the normal git workflow (beta first).
- **Assets and `EffectMap.json` are gitignored gamedata** → prod needs a manual sync of
  `Squad.nitro` and the EffectMap edit. A green deploy does not carry them.
- CHANGELOG.md entry required (player-facing change).
