# `:zombies` stress-test command

**Date:** 2026-09-01
**Status:** Approved

## Purpose

A staff command to stress-test room load by spawning N zombie NPCs that clone a
target player's name and look and walk randomly around the room. Exercises the
room tick cycle, pathfinder, and movement-packet broadcast with a controllable
avatar count. Bare `:zombies` cleans them all up.

## Usage

- `:zombies <username> <quantity>` — spawns `<quantity>` zombies cloning
  `<username>`'s name, look, and gender. Target must be in the caller's room.
- `:zombies` — despawns every zombie in the caller's room.

Staff-only: permission `command_zombies`, seeded at `group_id` 5.

## Architecture

New `ZombiesCommand : IChatCommand` in
`emulator/HabboHotel/Rooms/Chat/Commands/Moderator/`. Implements
`IChatCommand` (not `ITargetChatCommand`) because bare `:zombies` has no
target; the command resolves the username argument itself via the room's user
manager. Auto-registered by the existing DI assembly scan.

### Zombies are ephemeral RoomBots

Each zombie is a `RoomBot` constructed in memory and deployed with
`RoomUserManager.DeployBot(bot, null)`:

- AI type `"generic"`, walking mode `"freeroam"` — the existing `GenericBot`
  freeroam branch picks a random walkable square every 5–15 ticks
  (`GetRandomWalkableSquare`), which is the desired random wandering.
- Name / Look / Gender copied from the target Habbo. Empty speech list,
  `AutomaticChat` off.
- Initial position: a random walkable square per zombie so they spread out
  instead of stacking at the door.
- **No database rows.** Spawn and despawn are purely in-memory
  (`RemoveBot` verified to do no DB work for bots).

### Identity: negative bot ids

`RoomUserManager._bots` is keyed by `BotData.Id`; duplicate ids silently
overwrite entries. Zombies take unique negative ids from a static
`Interlocked.Decrement` counter. Negative id doubles as the zombie sentinel:

- No collision with real (positive, DB-backed) bot ids.
- Despawn scans room users for `IsBot && BotData.Id < 0` and calls
  `RemoveBot(virtualId, false)` on each.

### Cap and validation

- Hard cap **100 zombies per room**, counted across repeated invocations
  (existing zombie count + requested ≤ 100; excess requests are clamped and
  the whisper reports the clamp).
- Unknown/absent target, non-numeric or ≤ 0 quantity → whisper usage text.
- Whisper feedback on success: spawned count and room total; removed count on
  cleanup.

### Inherited behavior (intentional)

`DeployBot` applies the bot identifier effect (187) to every non-pet bot, so
zombies glow like other NPCs. Kept deliberately — zero code and makes them
easy to spot for cleanup.

## Ship-with

- SQL migration `61_ZombiesCommand.sql` in `emulator/Resources/SQLs/Updates/`
  seeding `command_zombies` at group 5 (idempotent `INSERT IGNORE`;
  auto-applies on deploy).
- `CHANGELOG.md` entry.
- Emulator version bump per deploy convention.

## Testing

Manual in-game testing on beta (user's preferred flow): spawn against a
target, watch wandering and room performance, then `:zombies` to clean up.
Verify despawn leaves real placed bots untouched.
