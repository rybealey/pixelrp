# Realtime Rank/Tier Updates + Shift Announcements — Design

**Date:** 2026-08-31 · **Scope:** emulator + client · **Branch:** beta

## Problem

Rank/tier changes (superhire today, promotions later) must reflect in real
time in the Corporations window, the RP profile, and the infostand — and
clocking in/out should be announced to the room with the same blue shout
bubble as being hired (bubble 4).

## Design (approved)

### Emulator

- `CorporationUtility.BroadcastEmployment(int userId)`: compose the
  employment packet (`ComposeFor`, corpId 0 when unemployed) and send it
  HOTEL-WIDE via `ClientManager.SendPacket`, then call
  `ShiftManager.RefreshSession(userId)`. This is the one call every future
  employment mutation makes.
- SuperHire and SuperFire replace their room-scoped broadcast blocks with
  `BroadcastEmployment` (theatrical shouts unchanged; superfire's
  interrupt-then-delete ordering unchanged).
- `ShiftManager.RefreshSession(userId)`: no-op off duty; on duty, re-run
  the job query and, under the session lock, update `CorpName`, `RankPay`
  (next payday pays the new wage) and `WorkingMotto`, then re-apply the
  motto so the infostand flips instantly. A shared `BuildWorkingMotto`
  helper keeps StartShift and RefreshSession identical.
- Shift announcements: `StartShift` and `StopShift` shout in the player's
  room via `roomUser.OnChat(4, "*has started their shift at {corp}*", true)`
  / `"*has ended their shift at {corp}*"` — bubble 4, the hired-target
  bubble. Auto-interrupts (idle, disconnect, superfire) stay quiet.

### Client

- Corporations window: listen for `RpUserCorpEvent`; while the window is
  open, refetch the selected corp's detail so the roster re-renders live.
- Profile and infostand already consume the packet - the hotel-wide
  broadcast is what extends their realtime beyond the target's room.

## Out of scope

Promotion commands themselves; announcing auto-interrupts.

## Files

- `emulator/HabboHotel/Corporations/CorporationUtility.cs`, `ShiftManager.cs`
- `emulator/.../Moderator/SuperHireCommand.cs`, `SuperFireCommand.cs`
- `client/src/components/rp-corporations/RpCorporationsView.tsx`
- `CHANGELOG.md`

## Verification

Both build gates; in-game: superhire an on-duty player to a new rank with
a second account's corp window/profile open - everything updates without
reopening, the motto flips, and the next payday pays the new wage;
:startwork/:stopwork shout in the room with the blue bubble.
