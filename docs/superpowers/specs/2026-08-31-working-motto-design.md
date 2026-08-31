# Working Motto — Design

**Date:** 2026-08-31 · **Scope:** emulator only · **Branch:** beta

## Problem

While a player is on duty (shift system, `:startwork`), their infostand
motto should read `[WORKING] <corporation> · <rank> <tier>` so everyone in
the room can see they're working, reverting to the RP-managed motto (e.g.
"Citizen") when the shift ends. Mottos are never player-editable
(`ChangeMottoEvent` is a deliberate no-op), so the "previous value" is
always the staff/system-set `users.motto`.

## Design (approved)

**Server-side, DB-untouched.** The working motto exists only in memory and
on the wire; `users.motto` is never written by the shift system.

- **StartShift** (after the on-duty whisper): build the working motto -
  `[WORKING] {corpName} · {rankName}` plus a space and the roman tier
  numeral (I-V) when the employee's tier >= 1; no numeral for no-tier
  leadership ranks (tier 0). Store nothing extra: set `habbo.Motto` in
  memory and broadcast the same user-change packet the stock motto handler
  used (see the removed handler's git history / other UserChangeComposer
  call-sites for the exact composer + room broadcast pattern).
  The ShiftSession query already joins rank; it additionally selects the
  rank name it already has, the employee tier, and the rank's `tiers`
  ceiling to decide numeral vs none.
- **Shift end with a live client** (StopShift, InterruptForIdle,
  superfire via the resolving overload): reload the true motto with a
  one-column query (`SELECT motto FROM users WHERE id = @userId`), set
  `habbo.Motto`, broadcast the user-change packet.
- **Disconnect / crash**: do nothing - the DB motto was never touched, so
  the next login loads the real value. (The disconnect save does not
  persist motto; verified.)
- The middot in the motto is safe: mottos render only in web-font UI
  (infostand, profile), never in Volter surfaces.

## Out of scope

- Any client change (the infostand already re-renders on the user-change
  packet), any schema change, motto editing (stays locked).

## Files

- `emulator/HabboHotel/Corporations/ShiftManager.cs`
- `CHANGELOG.md`

## Coordination

The user-launched task chip "Lock ShiftManager disconnect fallback flush"
is running in a separate session and edits the same file; rebase this work
on top of its pushed commit (or wait for it) before implementing.

## Verification

Emulator docker sdk:7.0 build passes; user tests in-game on beta:
:startwork shows `[WORKING] San Francisco Police Department · Officer II`
on the infostand for other players, :stopwork restores "Citizen", relog
mid-shift comes back with the real motto. Deploy commit tagged
`(bump emulator)`.
