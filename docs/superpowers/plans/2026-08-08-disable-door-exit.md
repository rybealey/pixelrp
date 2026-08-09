# Disable Door-Tile Walk-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Spec: `docs/superpowers/specs/2026-08-08-disable-door-exit-design.md`

**Goal:** Stepping on a room's door tile no longer removes the user from the room; the hotel-view exit packet only works for staff.

**Architecture:** Two surgical emulator edits. (1) Delete the walk-cycle check in `ProcessUserMovement` that kicks a non-bot user to hotel view when a step lands on `Model.DoorX/DoorY` — the fall-through code already treats the tile as a normal tile. (2) Early-return in `GoToHotelViewEvent` unless `Habbo.IsStaff`.

**Tech Stack:** C#/.NET (PlusEMU fork, submodule `emulator/`, branch `pixelrp`), Docker Compose dev stack.

## Global Constraints

- No unit-test project exists in PlusEMU: each task's test cycle is compile (`docker compose build emulator`), boot to `EMULATOR -> READY!`, plus live browser assertions as specified.
- Emulator commits go on `emulator/` branch `pixelrp`; after pushing, bump the root submodule pointer and add a player-facing `CHANGELOG.md` entry in the same push (project discipline).
- `Habbo.IsStaff` (`Rank >= 5`, `emulator/HabboHotel/Users/Habbo.cs:68`) is the staff test — do not invent a new rank check.
- Do NOT touch `RemoveUserFromRoom`, the autokick `toRemove` path, bot walk logic, entry/spawn logic, or the furni-placement/`GameMap` `DoorX` checks (they block placing furni on the door tile and set up walkability — unrelated).

---

### Task 1: Emulator edits + compile

**Files:**
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs:802-807` (inside `ProcessUserMovement`)
- Modify: `emulator/Communication/Packets/Incoming/Navigator/GoToHotelViewEvent.cs`

**Interfaces:**
- Consumes: `Habbo.IsStaff` (existing, `Rank >= 5`).
- Produces: no new interfaces; behavior change only.

**Steps:**

- [ ] **Step 1: Remove the door-exit check in `RoomUserManager.cs`.** In `ProcessUserMovement`, delete exactly this block (currently lines 802–807), replacing it with the one-line comment shown, so the step falls through to the normal walk-on-furni/`UpdateUserStatus` handling:

```csharp
// DELETE this block:
                        if (user.X == _room.GetGameMap().Model.DoorX && user.Y == _room.GetGameMap().Model.DoorY && !toRemove.Contains(user) && !user.IsBot)
                        {
                            toRemove.Add(user);
                            removed = true;
                            return updated;
                        }

// REPLACE with:
                        // pixelrp: the door tile is not an exit — players leave rooms via
                        // teleports (staff also via navigator/hotel-view), never by walking out.
```

  The `removed` out-param stays initialized to `false` at the top of the method and the `toRemove` list is still used by the autokick path, so nothing else changes.

- [ ] **Step 2: Staff-gate `GoToHotelViewEvent.cs`.** Replace the `Parse` body so the whole file reads:

```csharp
using Plus.Communication.Packets.Incoming.Rooms;
using Plus.HabboHotel.GameClients;
using Plus.HabboHotel.Rooms;

namespace Plus.Communication.Packets.Incoming.Navigator;

internal class GoToHotelViewEvent : RoomPacketEvent
{
    public override Task Parse(Room room, GameClient session, IIncomingPacket packet)
    {
        // pixelrp: hotel view is staff-only. The stock client has no leave-room UI,
        // so an in-room exit request from a non-staff user can only come from a
        // modified client — ignore it. (RoomPacketEvent already no-ops when the
        // user is not in a room, so error/doorbell flows never reach this.)
        if (!session.GetHabbo().IsStaff) return Task.CompletedTask;
        room.GetRoomUserManager()?.RemoveUserFromRoom(session, true);
        return Task.CompletedTask;
    }
}
```

- [ ] **Step 3: Compile and boot.**

```bash
docker compose build emulator 2>&1 | tail -3
docker compose up -d emulator
```

Then check logs for `EMULATOR -> READY!` (`docker compose logs emulator | tail -20`). Expected: clean build, clean boot.

- [ ] **Step 4: Commit on the emulator submodule (branch `pixelrp`).**

```bash
git -C emulator add HabboHotel/Rooms/RoomUserManager.cs Communication/Packets/Incoming/Navigator/GoToHotelViewEvent.cs
git -C emulator commit -m "feat(rooms): door tile no longer exits the room; hotel-view packet staff-only"
```

### Task 2: Live verification (local dev)

**Files:** none (verification only).

**Steps:**

- [ ] **Step 1: Walk-out test as regular user.** Log in as `ClaudeTest` (non-staff, SSO-ticket flow) on the local dev client, enter a room, click the door/entry tile to walk onto it. Expected: avatar walks onto the tile and stands there — no exit to hotel view, no disconnect. Walk off and back on once more to confirm the tile is fully normal.
- [ ] **Step 2: Entry-over-occupied-door test.** While `ClaudeTest` stands on the door tile, have a second account (or the bot) enter the room. Expected: entry succeeds (same handling as any occupied spawn tile), no crash in `docker compose logs emulator`.
- [ ] **Step 3: Staff walk test.** As a staff account (rank ≥ 5), walk onto the door tile. Expected: also no exit (the removal applies to everyone).
- [ ] **Step 4: Packet gate.** No legit client path sends `DesktopViewComposer` while in a room (toolbar has no leave button; error/doorbell flows fire outside rooms and are filtered by `RoomPacketEvent`), so verify the gate by code inspection of the committed diff: non-staff → early return; staff → unchanged `RemoveUserFromRoom`. Confirm no emulator log errors after the session.

### Task 3: Changelog, submodule bump, push

**Files:**
- Modify: `CHANGELOG.md` (player-facing entry)
- Modify: root submodule pointer for `emulator/`

**Steps:**

- [ ] **Step 1: Push the emulator commit.**

```bash
git -C emulator push origin pixelrp
```

- [ ] **Step 2: Changelog entry.** Add under today's date in `CHANGELOG.md`, matching the file's existing entry style:

```markdown
- Room doorways no longer dump you out of the room — the entrance tile is now
  a normal tile you can walk on. Move between rooms using the teleport arrows.
```

- [ ] **Step 3: Bump submodule + commit + push main.**

```bash
git add emulator CHANGELOG.md
git commit -m "chore: bump emulator (door tile no longer exits room)"
git push
```

### Task 4: Deploy to VPS

**Steps:**

- [ ] **Step 1: Pull + rebuild on the VPS** (no SQL, no asset sync needed for this change):

```bash
ssh <vps> 'cd <deploy-dir> && git pull --recurse-submodules && docker compose -f compose.prod.yaml build emulator && docker compose -f compose.prod.yaml up -d emulator'
```

  (Use the VPS host/paths from the existing deploy routine; this change touches only the emulator image.)

- [ ] **Step 2: Prod smoke test.** Log in as `Claude` (prod test account), walk onto a door tile. Expected: no exit. Check emulator logs for errors.
