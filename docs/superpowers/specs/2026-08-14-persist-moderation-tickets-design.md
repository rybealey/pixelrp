# Moderation tickets survive an emulator restart — design

Date: 2026-08-14
Status: approved (full-fidelity persistence; SQL 22; durability only —
`CloseIssueDefaultActionEvent` left alone)

## Problem

Moderation tickets are never written to the database. The INSERT in
`Communication/Packets/Incoming/Moderation/SubmitNewTicketEvent.cs` is
commented out behind a `// TODO: Come back to this`, so
`moderation_tickets` is always empty and `ModerationManager`'s in-memory
`_modTickets` dictionary is the only store. Every emulator restart —
including every deploy — silently discards open tickets that staff have not
yet picked or closed.

The report flow itself was fixed on 2026-08-14 (commit `4f58cea`); this is
the remaining durability gap, currently recorded under "Known issues" in the
changelog.

Uncommenting the INSERT is not sufficient, for three reasons found while
exploring:

1. **Ticket ids come from an in-process counter.** `TryAddTicket` assigns
   `ticket.Id = _ticketCount++` starting at 1. Once rows exist, those ids
   collide with persisted ones after a restart.

2. **A ticket cannot be rebuilt from a row as the type is shaped today.**
   `ModerationTicket` holds live `Habbo` references for sender, reported and
   moderator, plus a `RoomData` reference. `PlusEnvironment.GetHabboById`
   returns `null` for any offline user — its offline-load path is commented
   out (`PlusEnvironment.cs:237`) — so a restored ticket would carry null
   users and render with id `0` and a blank username.

3. **The commented-out INSERT stored the wrong field.** It wrote `Category`
   into the `type` column. The client reads the composer's `Type` field as
   `categoryId` — the label shown in the Open Issues list, mapped through
   `GetIssueCategoryName` — and reads `Category` as `reportedCategoryId`.
   Both fields have to survive, and the shipped table only has `type`.

## Decisions (from brainstorming)

- **Full fidelity.** A ticket that survives a restart is indistinguishable
  from a fresh one: correct category label, correct usernames, and the
  reporter's quoted chat lines still open in the chatlog view. This costs
  two new columns.
- **Durability only.** `CloseIssueDefaultActionEvent` is an empty stub that
  does nothing today, so it has no state change to write through. Making the
  mod tool's default-action close button work is a separate behaviour fix
  and is recorded as a known issue instead.
- **Ids come from the database.** The `_ticketCount` counter is deleted
  rather than seeded past the max existing id — with `AUTO_INCREMENT`
  assigning ids there is no counter to keep in sync.
- **The manager owns the SQL.** `ModerationManager` already holds
  `IDatabase`; write-through lives there rather than being scattered across
  four packet handlers.

## Changes

### Schema — `emulator/Resources/SQLs/Updates/22_PersistModerationTickets.sql`

```sql
ALTER TABLE `moderation_tickets`
    ADD COLUMN `category` int(11) NOT NULL DEFAULT 0 AFTER `type`,
    ADD COLUMN `reported_chats` text NULL DEFAULT NULL AFTER `message`;
```

`moderation_tickets` already ships in `Resources/SQLs/Original Database.sql`
with `score`, `type`, `status`, `sender_id`, `reported_id`, `moderator_id`,
`message`, `room_id`, `room_name` and `timestamp`, so only the two new
columns are needed. `status` is already the enum
`('open','picked','resolved','abusive','invalid','deleted')`.

`reported_chats` holds a JSON array of the quoted lines, serialised with
`System.Text.Json` (already a dependency — see `RevisionsCache.cs`). JSON
rather than newline-joining because the lines are player-controlled text.
The column is nullable and a null or unparseable value loads as an empty
list, so a row written by anything else cannot throw during startup.

Applied the same way as previous updates — by hand against the running
database, locally and on prod — not by editing `Original Database.sql`.

### `HabboHotel/Moderation/ModerationTicket.cs`

Replace the object references with the identifiers the packets actually
read:

- `Habbo Sender` → `int SenderId`, `string SenderUsername`
- `Habbo Reported` → `int ReportedId`, `string ReportedUsername`
- `Habbo Moderator` → `int ModeratorId` (`0` = unpicked), `string ModeratorUsername`
- `RoomData Room` → `uint RoomId` (`0` = none), `string RoomName`

`Type`, `Category`, `Timestamp`, `Priority`, `Answered` and `ReportedChats`
are unchanged. Two constructors: one taking the live `Habbo`/`RoomData`
objects for a fresh report (so `SubmitNewTicketEvent` reads as it does
today), one taking the flat values for a database row.

`GetStatus(int id)` keeps its current contract, rewritten against
`ModeratorId`: `0` → `1` (open); picked by the asking moderator and not
answered → `2`; otherwise `3`.

This is what makes a restored ticket render correctly, and it is safe
because every consumer only ever reads `.Id` and `.Username` off those
`Habbo` references —
`ModeratorSupportTicketComposer`, `ModeratorTicketChatlogComposer`,
`CloseTicketEvent`, and `ModerationManager.UserHasTickets`.
`GetModeratorTicketChatlogsEvent` already re-resolves the room through
`RoomFactory.TryGetData(ticket.Room.Id)`, which becomes
`TryGetData(ticket.RoomId)` with the null guard becoming `RoomId == 0`.

### `HabboHotel/Moderation/ModerationManager.cs` (+ `IModerationManager`)

- `TryAddTicket(ticket)` — INSERT with `status = 'open'` and
  `moderator_id = 0`, take the auto-increment id as `ticket.Id`, then cache.
  `_ticketCount` is removed.
- `PickTicket(ticket, moderator)` — set `ModeratorId`/`ModeratorUsername`,
  write `status = 'picked'` and `moderator_id`.
- `ReleaseTicket(ticket)` — clear the moderator, write `status = 'open'`,
  `moderator_id = 0`.
- `CloseTicket(ticket, status)` — set `Answered = true`, write the final
  status.
- `Init()` — load `WHERE status IN ('open','picked')` and repopulate
  `_modTickets`, logging the count alongside the existing startup lines.
  Closed tickets stay in the table as history and are not reloaded.

Status mapping on close, from the result `CloseTicketEvent` reads:
`1` → `invalid`, `2` → `abusive`, `3` → `resolved`. A player deleting their
own pending call (`CallForHelpPendingCallsDeletedEvent`) writes `deleted`.

### Packet handlers

`PickTicketEvent`, `ReleaseTicketEvent`, `CloseTicketEvent` and
`CallForHelpPendingCallsDeletedEvent` call the manager methods above instead
of assigning `ticket.Moderator` / `ticket.Answered` directly.
`SubmitNewTicketEvent` drops the commented-out INSERT block and keeps its
`user_info.cfhs` increment.

## Error handling

- **A failed INSERT must not lose the report.** If the insert throws, it is
  logged and the ticket is still cached with a negative id, so it reaches
  staff for the current session and is visibly not persisted. Silently
  dropping a report is exactly the failure that commit `4f58cea` fixed; a
  database hiccup should not reintroduce it.
- **Rows for users that no longer exist** are skipped at load with a log
  line, rather than loading a ticket that renders as a blank username.
- **Deleted rooms** still render a name, because `room_name` is captured at
  creation; the chatlog view's existing `RoomFactory.TryGetData` guard
  already covers the room itself being gone.
- **Write-through failures on state change** are logged and do not abort the
  handler — the in-memory state and the packet to staff still go out, and
  the worst case degrades to today's behaviour for that one ticket.

## Verification

Staff receive the ticket list through `ModeratorInitComposer` at login
(`SSOTicketEvent.cs:129`), which is the path a restart test exercises. Two
client sessions per `docker/nitro/README.md`, using the `ClaudeTest`
account as reporter and a staff account as moderator:

1. Submit a report with quoted chat lines. Confirm one row in
   `moderation_tickets` with `status = 'open'`, the right `sender_id`,
   `reported_id`, `type`, `category`, `message` and a populated
   `reported_chats`.
2. Restart the emulator. Log the staff account back in and confirm the
   ticket is listed in the Tickets panel with the correct reporter and
   reported usernames and the correct category label, and that its Chatlog
   still shows the quoted lines.
3. Pick it; confirm `status = 'picked'` and `moderator_id` in the database.
   Restart again and confirm it returns still picked, to the right
   moderator.
4. Close it; confirm the final status and that it does not reload on the
   next restart.
5. Confirm the reporter is still told their existing call is open when they
   try to submit a second report against a ticket that was restored rather
   than created this session.

## Out of scope

`CloseIssueDefaultActionEvent` is an empty stub, so the mod tool's
default-action close button does nothing. Recorded as a known issue for a
separate change.
