# Corporation Headquarters, Authorizations & Emergencies — design

2026-08-31. Spans three repos: emulator (schema, packets, shift-gating),
the nitro-renderer yarn patch inside the `client/` submodule (new packets),
and the client UI. Ships to beta only.

## Overview

Room owners/staff can tie a room to a corporation as its **headquarters**,
control which **ranks** may work there, and set which outside emergency
services (**Medical / Police / Staff**) may work in the room. Working
(`:startwork` shifts) becomes room-gated: an employee of a corp that has an
HQ can only be on the clock somewhere they're actually permitted to work.

This is the first room↔corporation link in the codebase. It hangs off the
Room Settings › Roleplay tab's Corporations section, whose three links
(Headquarters, Authorizations, Emergencies) currently render placeholders.

## Locked product decisions

- **Work gating:** a corp with **≥1 HQ room** → its employees may only be on
  duty where permitted (HQ+rank, or a matching emergency allowance). A corp
  with **no HQ** → work anywhere, exactly as today. Nothing breaks on
  rollout because every existing corp starts with no HQ.
- **Default rank authorization:** assigning a room as a corp's HQ seeds
  **all** of that corp's ranks as authorized. Staff then uncheck.
- **Multiplicity:** a corp may have **many** HQ rooms; a room is HQ for **at
  most one** corp.
- **Enforcement is continuous:** the existing per-minute shift tick
  re-checks permission and clocks out anyone no longer permitted, reusing
  the "fallen asleep on duty" interrupt path. This also makes mid-shift
  config changes (reassigning a room, deauthorizing a rank, toggling an
  emergency service) resolve within one minute with no separate cleanup.
- **Emergency services are corp-based** via a per-corp `service_type`:
  `medical` = HMMC, `police` = SFPD, `staff` = PixelRP Leadership (PRPL),
  everything else none. Seeded by acronym. There is no rank≥5 special case.
- **Emergency access default:** every room admits Medical, Police and Staff
  by default (all three room flags default on).
- **Who edits what:** Headquarters and Authorizations are **staff-only**
  (rank ≥ 5, server-enforced). Emergencies is editable by **room owner or
  staff** (whoever can open Room settings).

## Data model — `emulator/Resources/SQLs/Updates/53_CorporationHeadquarters.sql`

Highest existing update file is `52_CorpManagement.sql`; this is `53`. Every
`ALTER` is guarded with an `information_schema` existence check + `PREPARE`
(the prod `rooms`/`rp_corporations` tables predate this and the deploy runs
under `set -e`) — mirror `22_PersistModerationTickets.sql`.

- `rooms.corporation_id INT NOT NULL DEFAULT 0` — the room's HQ corp; `0` =
  not an HQ.
- `rooms.allow_medical`, `rooms.allow_police`, `rooms.allow_staff` —
  `enum('0','1') NOT NULL DEFAULT '1'` each (mirrors `is_safe_zone`; loaded
  via `RoomFactory.ToBool`, per the tinyint→bool trap).
- `rp_corporations.service_type VARCHAR(12) NOT NULL DEFAULT ''`, then
  `UPDATE ... SET service_type='medical' WHERE acronym='HMMC'`,
  `='police' WHERE acronym='SFPD'`, `='staff' WHERE acronym='PRPL'`
  (idempotent; by acronym, not id).
- New table `rp_hq_room_ranks (room_id INT NOT NULL, rank_id INT NOT NULL,
  PRIMARY KEY (room_id, rank_id))` — a row means "this rank may work in this
  room." Absence = not authorized. `CREATE TABLE IF NOT EXISTS`.

**Assignment writes (server-side, transactional):**
- Set HQ to corp C: `UPDATE rooms SET corporation_id=C`; `DELETE FROM
  rp_hq_room_ranks WHERE room_id=R`; `INSERT` one row per `rp_corporation_ranks`
  id of C (default all authorized).
- Clear HQ (C = 0): `UPDATE rooms SET corporation_id=0`; `DELETE FROM
  rp_hq_room_ranks WHERE room_id=R`.
- Toggle rank K: validate K belongs to R's corp, then `INSERT IGNORE` /
  `DELETE` the `(R,K)` row.
- Toggle emergency category: `UPDATE rooms SET allow_<cat>=@v WHERE id=R`.

## Work-gating rule

For employee E (corp C, rank_id K, rank_order O) attempting to be on duty in
room R:

1. If C has **no** HQ rooms (`SELECT COUNT(*) FROM rooms WHERE
   corporation_id=C` == 0) → **permitted** anywhere (unchanged fallback).
2. Otherwise, if `R.corporation_id == C` (R is their own corp's HQ), the
   rank authorization is **definitive**: permitted iff a row `(R, K)` exists
   in `rp_hq_room_ranks`, else **denied**. (Rank auth wins here on purpose:
   an emergency fallback at your own HQ would make deauthorizing a rank a
   no-op for exactly the service corps that default their emergency flags
   on — so the emergency check does *not* apply at your own HQ.)
3. Otherwise (R is not their HQ) permitted iff **any** of:
   - `C.service_type == 'medical'` and `R.allow_medical`; or
   - `C.service_type == 'police'` and `R.allow_police`; or
   - `C.service_type == 'staff'` and `R.allow_staff`.
4. Else **denied**.

Implemented once as `ShiftManager.EvaluateWork(Habbo) -> (bool ok, string
reason)`, called at clock-in and on each minute boundary for on-duty
employees whose corp is HQ-gated.

## Packets

Four new wire ids. Per the header-collision rule, the emulator internal
`ClientPacketHeader`/`ServerPacketHeader` constant is set to the wire value
if that value is free among existing internal constants in that file, else
bumped into the `439xx` range with a `// <wire>` comment; the wire id in
`Resources/Revisions/1.6.6.json` (keyed by constant NAME) and the renderer
header constant are always the plain 39xx value. The implementer verifies
each id against BOTH header tables before assigning. Reuse existing
`RpGetCorpsComposer`/`RpCorpsEvent` (3948/3946) for the dropdown's corp
list.

**`RpRoomCorpComposer` (server→client, wire 3957)** — the room's full
roleplay-corp config, sent (a) alongside `RpRoomZoneComposer` in
`GetRoomSettingsEvent` and (b) echoed after every write:
```
int roomId
int corpId                     // 0 = no HQ
int rankCount                  // 0 when corpId == 0
  per rank: int rankId, int rankOrder, string rankName, int authorized(0/1)
int allowMedical(0/1)
int allowPolice(0/1)
int allowStaff(0/1)
```

**`RpSetRoomCorpEvent` (client→server, wire 3958)** — `int corpId` (0 =
clear). Gate: `room = CurrentRoom`; `room.CheckRights(session, true)` **and**
`session.GetHabbo().Rank >= 5`. Applies the set/clear + reseed, replies
`RpRoomCorpComposer`.

**`RpSetHqRankEvent` (client→server, wire 3959)** — `int rankId, int
authorized`. Same staff+rights gate; validates the rank belongs to the
room's corp; toggles the row; replies `RpRoomCorpComposer`.

**`RpSetEmergencyEvent` (client→server, wire 3960)** — `int category`
(0=medical, 1=police, 2=staff), `int enabled`. Gate: `CheckRights(session,
true)` only (owner or staff). Updates the room flag; replies
`RpRoomCorpComposer`.

All three write handlers use `session.GetHabbo()?.CurrentRoom` (like
`RpRoomZoneSaveEvent`), not a room id from the packet body, and update the
in-memory `Room` object (`CorporationId`, `AllowMedical/Police/Staff`) so
the tick sees changes immediately.

## Emulator changes (files)

- `Resources/SQLs/Updates/53_CorporationHeadquarters.sql` (new).
- `HabboHotel/Rooms/RoomData.cs` — add `int CorporationId`, `bool
  AllowMedical/AllowPolice/AllowStaff`; copy in the constructor.
- `HabboHotel/Rooms/Room.cs` — mirror the four (like `IsSafeZone`), used by
  the write handlers and the tick.
- `HabboHotel/Rooms/RoomFactory.cs` — load the four columns at the two build
  sites (≈ lines 55 & 98), `ToBool` for the three flags.
- `Communication/Packets/Incoming/ClientPacketHeader.cs` +
  `Communication/Packets/Outgoing/ServerPacketHeader.cs` — four constants.
- `Resources/Revisions/1.6.6.json` — four NAME→wire entries.
- `Communication/Packets/Outgoing/Rooms/Settings/RpRoomCorpComposer.cs` (new).
- `Communication/Packets/Incoming/Rooms/Settings/RpSetRoomCorpEvent.cs`,
  `RpSetHqRankEvent.cs`, `RpSetEmergencyEvent.cs` (new; ctor-injected
  `IDatabase`).
- `Communication/Packets/Incoming/Rooms/Settings/GetRoomSettingsEvent.cs` —
  send `RpRoomCorpComposer` right after the existing `RpRoomZoneComposer`.
- `HabboHotel/Corporations/ShiftManager.cs` — `EvaluateWork`; call it in
  `StartShift` (before `on_duty=1`); store `CorpId`, `RankId`, `HqGated` on
  `ShiftSession`; extend `TickSession` to clock out on a failed re-check via
  a new `InterruptForLeftWork` (shout, mirrors the fallen-asleep path).
- `HabboHotel/Corporations/CorporationUtility.cs` — a small helper if the
  HQ/service lookups are shared between the handlers and `ShiftManager`
  (e.g. `EvaluateWork` may live here beside `RequireManager`).

## Renderer patch (client submodule)

Add to the patched `@nitrots/nitro-renderer` and reseal (stacked-patch
procedure — `yarn patch -u` with the newest descriptor, edit, `yarn
patch-commit -s`, `yarn install`, grep node_modules to confirm both existing
and new symbols; commit package.json + yarn.lock + `.yarn/patches/*` **inside
the client submodule** and push `pixelrp`):

- `incoming/RpRoomCorpEvent.ts` (+ parser) — mirror the composer fields; export
  from `incoming/index.ts`; `IncomingHeader.RP_ROOM_CORP = 3957`; register in
  `NitroMessages.ts`.
- `outgoing/RpSetRoomCorpComposer.ts` (`corpId`), `RpSetHqRankComposer.ts`
  (`rankId, authorized`), `RpSetEmergencyComposer.ts` (`category, enabled`) —
  export from `outgoing/index.ts`; `OutgoingHeader.RP_SET_ROOM_CORP=3958`,
  `RP_SET_HQ_RANK=3959`, `RP_SET_EMERGENCY=3960`; register in
  `NitroMessages.ts`.

Never let a composer `_data` element be null/undefined (EvaWire desync);
booleans go as `1`/`0` ints for symmetry with the existing corp packets.

## Client UI

Room-corp state is hoisted into `NavigatorRoomSettingsView` (a
`useMessageEvent<RpRoomCorpEvent>` handler storing the parsed config, passed
down like `isSafeZone`/`setIsSafeZone` today), because the composer arrives
right after the settings data before the tab mounts.

`NavigatorRoomSettingsRoleplayTabView` stays the rail + router; the three
substantive pages become their own components in the same folder:

- **`RoleplayHeadquartersView.tsx`** — a corp `<select>` (a "None" option +
  every corp from `RpCorpsEvent`; current = `corpId`). On mount the tab
  sends `RpGetCorpsComposer` to populate options. On change →
  `RpSetRoomCorpComposer`. Editable only when `IsRpStaff()`; otherwise the
  select is disabled with a muted "Only staff can set a headquarters." note.
- **`RoleplayAuthorizationsView.tsx`** — if `corpId == 0`, a muted "Assign a
  headquarters first." note. Otherwise a checkbox per rank (from the
  composer's rank list, `authorized` flag, ordered by `rankOrder`). On
  toggle → `RpSetHqRankComposer`. Staff-only editable, same note pattern.
- **`RoleplayEmergenciesView.tsx`** — three checkboxes (Medical, Police,
  Staff) bound to `allowMedical/allowPolice/allowStaff`. On toggle →
  `RpSetEmergencyComposer`. Always editable (owner or staff opened the
  window); a short description line explains it admits outside services.

Zoning stays inline (it's tiny); Headquarters, Authorizations and
Emergencies are extracted as above. `IsRpStaff()` comes from the existing
HUD `RpStatsEvent` store.

## In-game copy (no em-dashes; pixel-font safe)

- Clock-in denied (not an allowed location): `You can only work at your
  headquarters or an approved location.`
- Clock-in denied (at HQ, rank not authorized): `Your rank isn't cleared to
  work here.`
- Continuous auto clock-out (room shout, fallen-asleep style): `{name} has
  clocked out - left the workplace.`

## Rollout & back-compat

- Existing corps start with no HQ → everyone keeps working anywhere until
  staff assign an HQ. Existing rooms default `corporation_id=0` and all three
  emergency flags on.
- The migration auto-applies on the beta deploy (`_applied_sql_updates`);
  three-repo change ships together (emulator + client submodule pointer),
  pushed to `beta`. Player-facing CHANGELOG entry to #planned. No merge to
  main until in-game verification.

## Non-goals (this pass)

- No UI to change a corp's `service_type` (data-seeded; a future `:command`
  or housekeeping surface can follow).
- No per-rank emergency granularity (emergency access is corp-wide, any
  rank).
- Emergencies does not require the room to have its own HQ — it is an
  independent room access policy.
