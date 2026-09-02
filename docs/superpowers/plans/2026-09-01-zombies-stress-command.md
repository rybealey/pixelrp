# `:zombies` Stress-Test Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A staff command `:zombies <username> <quantity>` that spawns ephemeral freeroaming NPC clones of a player for room load testing, and bare `:zombies` that removes them all.

**Architecture:** One new `IChatCommand` in the emulator that constructs in-memory `RoomBot`s (negative ids, no DB rows) with the target's name/look/gender and `"freeroam"` walking mode, deployed via the existing `RoomUserManager.DeployBot`. The existing `GenericBot` freeroam AI provides random wandering. One SQL migration seeds the staff permission.

**Tech Stack:** C# (.NET, Plus Emulator), MySQL migration, Docker build for verification.

**Spec:** `docs/superpowers/specs/2026-09-01-zombies-stress-command-design.md`

## Global Constraints

- The emulator is a **git submodule** at `emulator/` (branch `pixelrp`). Emulator code commits happen inside the submodule; the parent repo then bumps the submodule pointer.
- **No dotnet on this machine.** Compile-verify with `docker compose build emulator` from the repo root.
- **No unit-test infrastructure exists** in the emulator (`Tests/` is empty) and the user prefers manual in-game testing (see memory `pixelrp-manual-ingame-testing`). Steps use build verification; final verification is the user testing in-game on beta.
- Zombie cap: **100 per room** total across invocations; requests are clamped and the clamp is reported.
- Permission: `command_zombies`, `group_id` 5 (staff), seeded idempotently.
- No em-dashes in any in-game whisper text (pixel font renders them as music notes) — use plain sentences/hyphens.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: ZombiesCommand + permission migration (emulator submodule)

**Files:**
- Create: `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/ZombiesCommand.cs`
- Create: `emulator/Resources/SQLs/Updates/61_ZombiesCommand.sql`

**Interfaces:**
- Consumes: `IChatCommand` (`emulator/HabboHotel/Rooms/Chat/Commands/IChatCommand.cs`), `RoomBot` ctor (`emulator/HabboHotel/Rooms/AI/RoomBot.cs:52`), `RoomUserManager.DeployBot(RoomBot, Pet)` / `RemoveBot(int virtualId, bool kicked)` / `GetRoomUserByHabbo(string)` / `GetUserList()`, `Gamemap.GetRandomWalkableSquare()`.
- Produces: chat command `zombies` (auto-registered — the DI scan in `Program.cs:163` picks up any non-abstract `ICommandBase` implementor; no manual registration file exists).

- [ ] **Step 1: Write the command**

Create `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/ZombiesCommand.cs`:

```csharp
using Plus.HabboHotel.GameClients;
using Plus.HabboHotel.Rooms.AI;
using Plus.HabboHotel.Rooms.AI.Speech;

namespace Plus.HabboHotel.Rooms.Chat.Commands.Moderator;

/// <summary>
/// pixelrp stress testing: spawn ephemeral freeroaming NPC clones of a player
/// to load-test the room cycle, pathfinder, and movement broadcast. Zombies
/// live only in memory - negative bot ids, no DB rows - so bare :zombies
/// removes every one of them without touching real placed bots.
/// </summary>
internal class ZombiesCommand : IChatCommand
{
    private const int MaxZombiesPerRoom = 100;

    // Negative ids keep zombies clear of real (DB-backed) bot ids in
    // RoomUserManager._bots (keyed by BotData.Id, so duplicates would
    // silently overwrite) and double as the "is a zombie" marker.
    private static int _nextZombieId;

    public string Key => "zombies";
    public string PermissionRequired => "command_zombies";

    public string Parameters => "%username% %quantity%";

    public string Description => "Stress test: spawn freeroaming clones of a player. Bare :zombies removes them all.";

    public void Execute(GameClient session, Room room, string[] parameters)
    {
        if (parameters.Length == 0)
        {
            DespawnAll(session, room);
            return;
        }
        if (parameters.Length < 2 || !int.TryParse(parameters[1], out var quantity) || quantity <= 0)
        {
            session.SendWhisper("Usage: :zombies <username> <quantity> to spawn, :zombies to remove them all.");
            return;
        }
        var target = room.GetRoomUserManager().GetRoomUserByHabbo(parameters[0]);
        var habbo = target?.GetClient()?.GetHabbo();
        if (habbo == null)
        {
            session.SendWhisper("That user is not in this room.");
            return;
        }
        var existing = CountZombies(room);
        var toSpawn = Math.Min(quantity, MaxZombiesPerRoom - existing);
        if (toSpawn <= 0)
        {
            session.SendWhisper($"This room is already at the zombie cap ({MaxZombiesPerRoom}). Use :zombies to clear them first.");
            return;
        }
        // Sharing one empty list is safe: RoomBot only reads it at construction.
        var emptySpeech = new List<RandomSpeech>();
        for (var i = 0; i < toSpawn; i++)
        {
            // Spread spawns across the room so zombies don't stack on one tile.
            var square = room.GetGameMap().GetRandomWalkableSquare();
            var bot = new RoomBot(Interlocked.Decrement(ref _nextZombieId), room.RoomId, "generic", "freeroam",
                habbo.Username, "", habbo.Look, square.X, square.Y, 0, 0, 0, 0, 0, 0,
                ref emptySpeech, habbo.Gender, 0, session.GetHabbo().Id, false, 0, false, 0);
            var zombie = room.GetRoomUserManager().DeployBot(bot, null);
            room.GetGameMap().UpdateUserMovement(new(square.X, square.Y), new(square.X, square.Y), zombie);
        }
        var total = existing + toSpawn;
        session.SendWhisper(toSpawn < quantity
            ? $"Spawned {toSpawn} of {quantity} zombies cloning {habbo.Username} (hit the cap: {total}/{MaxZombiesPerRoom} in room)."
            : $"Spawned {toSpawn} zombie{(toSpawn == 1 ? "" : "s")} cloning {habbo.Username} ({total}/{MaxZombiesPerRoom} in room).");
    }

    private static void DespawnAll(GameClient session, Room room)
    {
        var zombies = room.GetRoomUserManager().GetUserList().ToList()
            .Where(IsZombie)
            .ToList();
        foreach (var zombie in zombies)
            room.GetRoomUserManager().RemoveBot(zombie.VirtualId, false);
        session.SendWhisper(zombies.Count == 0
            ? "No zombies in this room."
            : $"Removed {zombies.Count} zombie{(zombies.Count == 1 ? "" : "s")}.");
    }

    private static int CountZombies(Room room) =>
        room.GetRoomUserManager().GetUserList().ToList().Count(IsZombie);

    private static bool IsZombie(RoomUser user) =>
        user is { IsBot: true, IsPet: false, BotData.Id: < 0 };
}
```

Notes for the implementer:
- `ImplicitUsings` is enabled in `Plus Emulator.csproj`, so `System`, `System.Linq`, `System.Threading` (for `Interlocked`), and `System.Collections.Generic` need no using lines.
- The `RoomBot` ctor param order is `(id, roomId, type, walkingMode, name, motto, look, x, y, z, rotation, minX, minY, maxX, maxY, ref speeches, gender, dance, ownerId, automaticChat, speakingInterval, mixSentences, chatBubble)` — mirror of the deploy in `Communication/Packets/Incoming/Rooms/AI/Bots/PlaceBotEvent.cs:71`.
- `"generic"` maps to `BotAiType.Generic` in `BotUtility.GetAiFromString`; `"freeroam"` hits the random-walk branch in `HabboHotel/Rooms/AI/Types/GenericBot.cs:95`.
- The `UpdateUserMovement` call after deploy mirrors `PlaceBotEvent` (registers the bot on the game map at its spawn square).
- `DeployBot` auto-applies the bot identifier effect 187 — intentional, do not suppress.

- [ ] **Step 2: Write the permission migration**

Create `emulator/Resources/SQLs/Updates/61_ZombiesCommand.sql` (verify 61 is still the next free number with `ls emulator/Resources/SQLs/Updates/ | sort -V | tail -3` and renumber if not):

```sql
-- pixelrp stress testing: :zombies spawns freeroaming NPC clones of a player
-- and bare :zombies removes them. Staff-only (group 5), matching the other
-- staff commands. Idempotent.
INSERT INTO `permissions_commands` (`command`, `group_id`, `subscription_id`)
VALUES ('command_zombies', 5, 0)
ON DUPLICATE KEY UPDATE `group_id` = 5;
```

- [ ] **Step 3: Compile-verify via Docker**

From the repo root (`/Users/rybealey/Documents/Personal/pixelrp/plus`):

```bash
docker compose build emulator
```

Expected: build succeeds (the Dockerfile runs the .NET build; a compile error fails the image build). Fix any compile errors and rebuild until green.

- [ ] **Step 4: Commit in the emulator submodule**

```bash
cd emulator
git add "HabboHotel/Rooms/Chat/Commands/Moderator/ZombiesCommand.cs" "Resources/SQLs/Updates/61_ZombiesCommand.sql"
git commit -m "feat(commands): :zombies stress-test command (migration 61)

Staff command that spawns up to 100 ephemeral freeroaming NPC clones of a
target player (negative bot ids, no DB rows) to load-test the room cycle,
and removes them all with bare :zombies.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Confirm the submodule is on branch `pixelrp` before committing (`git branch --show-current`).

---

### Task 2: Parent repo bump + changelog

**Files:**
- Modify: `CHANGELOG.md` (repo root — new dated section at the top, below the maintainer comment block)
- Modify: `emulator` (submodule pointer bump)

**Interfaces:**
- Consumes: the emulator submodule commit from Task 1.
- Produces: a parent-repo commit on `beta` ready to push (push auto-deploys beta.pixelrp.co).

- [ ] **Step 1: Add the changelog entry**

At the top of `CHANGELOG.md`'s entries (immediately after the maintainer comment block), add — or if a `## 2026-09-01` section already exists at the top, add the bullet under its `### Added` heading instead:

```markdown
## 2026-09-01 — Staff stress testing

### Added

- Staff can now spawn a horde of harmless zombie clones of a player to stress
  test a room, and clear them all just as fast. If you see twenty copies of
  someone shuffling around, the hotel is being load-tested; they vanish
  without a trace.
```

- [ ] **Step 2: Commit the bump + changelog**

From the repo root:

```bash
git add emulator CHANGELOG.md
git commit -m "feat(commands): :zombies stress-test command (bump emulator + changelog)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Expected: `git show --stat HEAD` lists `CHANGELOG.md` and `emulator` (pointer change).

- [ ] **Step 3: Push for beta deploy (submodule first, then parent)**

The parent repo references the submodule commit, so the submodule must be pushed first or the beta deploy's submodule fetch fails:

```bash
cd emulator && git push origin pixelrp && cd .. && git push origin beta
```

Expected: both pushes succeed; the beta deploy workflow picks up the push to `beta` and migration 61 auto-applies on deploy (tracked in `_applied_sql_updates`).

- [ ] **Step 4: Hand off for manual in-game verification**

Do not screenshot-drive the client. Tell the user the command is live on beta and ask them to verify in-game:
- `:zombies <name> 20` on an in-room target spawns 20 wandering clones spread across the room (each glowing with the bot identifier effect).
- Repeat invocations accumulate and clamp at 100 with a whisper reporting the clamp.
- `:zombies` removes all of them and leaves real placed NPCs untouched.
- Bad input (`:zombies ghost 5` with no such user in room, `:zombies <name> 0`, `:zombies <name> abc`) whispers the expected errors.
