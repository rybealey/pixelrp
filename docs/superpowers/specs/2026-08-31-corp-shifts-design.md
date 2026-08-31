# Corporation Shifts (:startwork / :stopwork) — Design

**Date:** 2026-08-31 · **Scope:** emulator + renderer patch + client · **Branch:** beta

## Problem

Corporations have ranks with wages ("pay per 10 minutes of shift worked")
but no way to actually work a shift. Employees need `:startwork` /
`:stopwork` chat commands, a countdown-driven pay schedule that persists
across sessions and stop/start cycles, a per-minute ephemeral countdown
message, and shift counts that update in real time on the RP profile and
in the Corporations window.

## Design (approved)

### Data (migration `emulator/Resources/SQLs/Updates/48_CorporationShifts.sql`)

- `ALTER TABLE rp_corporation_employees ADD COLUMN pay_seconds int NOT NULL
  DEFAULT 0` - seconds banked toward the CURRENT 10-minute pay interval.
  Resets on payout, carrying any overflow (e.g. 605 banked → paid, 5 kept).
- Existing columns go live: `shift_seconds` (lifetime), `shift_seconds_week`
  (weekly), `on_duty`.
- Boot hygiene: on emulator startup, any row with `on_duty = 1` is stale
  (crash while on duty) - clear the flag. Progress in `pay_seconds` etc. is
  whatever the last minute-flush persisted, so at most ~1 minute is lost on
  a hard crash.

### Server: ShiftManager (`emulator/HabboHotel/Corporations/`)

In-memory `ShiftSession` per on-duty player: user id, session start (UTC),
DB baselines (pay/lifetime/weekly seconds), rank pay, last-flushed elapsed,
and the client reference for whispers. A single timer (1-second resolution
is unnecessary; 10s granularity is fine internally, minute boundaries drive
messages) iterates active sessions.

- **StartShift** (from `:startwork`): requires employment
  (`rp_corporation_employees` row) and not already on duty. Sets
  `on_duty = 1`, creates the session, whispers
  `You are now on duty. Next pay in X minute(s).` where
  X = ceil((600 - pay_seconds) / 60).
- **StopShift** (from `:stopwork`): banks elapsed seconds into
  `pay_seconds`, `shift_seconds`, `shift_seconds_week`, clears `on_duty`,
  removes the session, whispers
  `Off duty. Xm banked toward your next pay.` (minutes rounded down; plain
  hyphens only in all strings).
- **Tick (per active session, each minute boundary):**
  1. Flush accumulated seconds to the DB (single-row UPDATE) - crash
     safety and the source for other players' live views.
  2. If a 600-second boundary was crossed: **payout** - add the rank's
     `pay` to the player's credits, send the credits-update packet, whisper
     `Payday! You earned Xc.`, subtract 600 from the banked interval
     (overflow carries), and continue the shift.
  3. Otherwise whisper the countdown, singular/plural handled:
     `Next pay in 1 minute.` / `Next pay in X minutes.`
- **InterruptShift** (same banking as StopShift): called on disconnect (no
  message - the client is gone), on going idle/asleep (whispers
  `Your shift ended because you went idle. Xm banked toward your next pay.`),
  and on superfire (no extra message - the firing flow already notifies;
  interrupt FIRST, then delete the employee row). Working location: anywhere; room changes do not affect a shift.
- Pay is the RANK wage only; tier does not affect pay. Wages mint from the
  system (no corp treasury yet).

### Wire (appended fields, no new wire ids)

Composer and renderer parser updated together in the stacked patch:

- `RpCorpDetailComposer` / renderer `RpCorpDetailParser`: each employee
  entry gains `shiftSeconds` (lifetime) and `shiftSecondsWeek` - the DB
  value plus live elapsed for on-duty employees at compose time.
- `RpUserCorpComposer` / renderer parser: employment payload gains
  `shiftSeconds`, `shiftSecondsWeek`, `onDuty` (int 0/1) so the profile can
  show and tick counts.
- EvaWire discipline: never write undefined; field order appended at the
  END of each payload; both sides change in the same deploy.

### Client (nitro-react)

- **Corporations window employee cards:** the `Weekly: X · Total: Y` line
  renders real data, humanized (`47m`, `12h 3m`; minutes granularity,
  hours+minutes once >= 60m). While an employee is `onDuty`, the card ticks
  locally: capture `(baseSeconds, Date.now())` when the detail packet
  arrives and re-render each minute - no polling packets. The existing
  Show-on-cards toggles govern the line as today.
- **RP profile:** the employment card gains the same shift-count line with
  the same local ticking while `onDuty`, plus an "On duty" indicator
  consistent with the corps window's presence colors.

### Commands

`:startwork` and `:stopwork` registered as player commands (no staff gate,
no permission row - available to everyone; the commands themselves check
employment and reply with a helpful whisper if the player has no job or is
already in the requested state).

## Out of scope

- Weekly reset of `shift_seconds_week` (needs a scheduled job later; the
  counter accumulates until then).
- Tier-based pay multipliers, corp treasuries/stock consumption, workplace
  or zone requirements.
- Any change to hiring (superhire/superfire) beyond the interrupt hook.

## Files

- `emulator/Resources/SQLs/Updates/48_CorporationShifts.sql`
- `emulator/HabboHotel/Corporations/ShiftManager.cs` (new)
- Emulator command classes + registration, RoomUserManager idle hook,
  disconnect hook, SuperFireCommand interrupt, both corp composers
- `client/.yarn/patches/` (renderer parser updates, stacked)
- `client/src/components/rp-corporations/RpCorporationsView.tsx/.scss`
- `client/src/components/rp-profile/RpProfileView.tsx/.scss` (+ its state)
- `CHANGELOG.md`

## Verification

Emulator `dotnet build` (sdk:7.0 container) and client `yarn build` pass;
user tests in-game on beta: startwork → minute whispers → payday at the
right minute → stopwork mid-interval → relog → startwork resumes the
remainder; corp window and profile tick while a second account watches.
Deploy commit tagged `(bump client + emulator)`.
