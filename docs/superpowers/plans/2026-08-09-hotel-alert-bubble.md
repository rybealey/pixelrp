# `:ha` Hotel Alert Bubble Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Spec: `docs/superpowers/specs/2026-08-09-hotel-alert-bubble-design.md`

**Goal:** Staff (rank ≥ 5) type `:ha <message>` and every online player sees the message as the client's standard INFO notification bubble (the moderation-disclaimer format), replacing the stock modal popup.

**Architecture:** Repoint the existing `HotelAlertCommand` from `BroadcastMessageAlertComposer` (modal) to a hotel-wide `RoomNotificationComposer` broadcast carrying `display=BUBBLE` + `message`, which the unmodified client already renders via `showSingleBubble(..., INFO)`. One SQL row update lowers the permission gate from rank group 8 to 5.

**Tech Stack:** C#/.NET (PlusEMU fork, submodule `emulator/`, branch `pixelrp`), MySQL 8, Docker Compose dev stack. No client changes.

## Global Constraints

- No unit-test project exists in PlusEMU: the test cycle is compile (`docker compose build emulator`), boot to `EMULATOR -> READY!`, plus live browser assertions.
- Emulator commits go on `emulator/` branch `pixelrp`; after pushing, bump the root submodule pointer and add a player-facing `CHANGELOG.md` entry in the same push (project discipline).
- The command keeps key `ha` and permission `command_hotel_alert`; message only (no "— Username" suffix); empty-message whisper guard stays.
- Do NOT touch the client, `BroadcastMessageAlertComposer` itself (other callers exist), or any other command.

---

### Task 1: Repoint HotelAlertCommand + SQL 17 + compile

**Files:**
- Modify: `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/HotelAlertCommand.cs`
- Create: `emulator/Resources/SQLs/Updates/17_HotelAlertRank5.sql`

**Interfaces:**
- Consumes: existing `RoomNotificationComposer(string type, Dictionary<string, string> values)` (`Communication/Packets/Outgoing/Rooms/Notifications/RoomNotificationComposer.cs`), existing `IGameClientManager.SendPacket`, existing `CommandManager.MergeParams`.
- Produces: no new interfaces; behavior change + one permission-row update.

**Steps:**

- [ ] **Step 1: Rewrite `HotelAlertCommand.cs`** so the file reads exactly:

```csharp
using Plus.Communication.Packets.Outgoing.Rooms.Notifications;
using Plus.HabboHotel.GameClients;

namespace Plus.HabboHotel.Rooms.Chat.Commands.Moderator;

internal class HotelAlertCommand : IChatCommand
{
    private readonly IGameClientManager _gameClientManager;
    public string Key => "ha";
    public string PermissionRequired => "command_hotel_alert";

    public string Parameters => "%message%";

    public string Description => "Send a bubble notification to the entire hotel.";

    public HotelAlertCommand(IGameClientManager gameClientManager)
    {
        _gameClientManager = gameClientManager;
    }

    public void Execute(GameClient session, Room room, string[] parameters)
    {
        if (!parameters.Any())
        {
            session.SendWhisper("Please enter a message to send.");
            return;
        }
        var message = CommandManager.MergeParams(parameters);
        // pixelrp: hotel alerts render as the client's INFO notification bubble
        // (display=BUBBLE path in useNotification), not the modal popup.
        _gameClientManager.SendPacket(new RoomNotificationComposer("hotel.alert",
            new Dictionary<string, string> { { "display", "BUBBLE" }, { "message", message } }));
    }
}
```

  (The `using Plus.Communication.Packets.Outgoing.Moderation;` line from the old version is removed — `BroadcastMessageAlertComposer` is no longer referenced.)

- [ ] **Step 2: Create `emulator/Resources/SQLs/Updates/17_HotelAlertRank5.sql`:**

```sql
-- :ha hotel alert usable by all staff (rank >= 5), matching the project's
-- staff convention (client isMod / Habbo.IsStaff). Stock mapping was 8.
UPDATE `permissions_commands` SET `group_id` = '5' WHERE `command` = 'command_hotel_alert';
```

- [ ] **Step 3: Compile and boot:**

```bash
docker compose build emulator 2>&1 | tail -3
docker compose up -d emulator
```

Check `docker compose logs emulator | tail -20` for `EMULATOR -> READY!`. Expected: clean build, clean boot.

- [ ] **Step 4: Apply SQL 17 locally and restart the emulator** (permissions load at boot):

```bash
docker compose exec -T db mysql -upixelrp -p"changeme-local" pixelrp < emulator/Resources/SQLs/Updates/17_HotelAlertRank5.sql
docker compose exec -T db mysql -upixelrp -p"changeme-local" pixelrp -e "SELECT command, group_id FROM permissions_commands WHERE command='command_hotel_alert';"
docker compose restart emulator
```

Expected: the SELECT shows `group_id = 5`; emulator reboots to READY.

- [ ] **Step 5: Commit on the emulator submodule (branch `pixelrp`):**

```bash
git -C emulator add HabboHotel/Rooms/Chat/Commands/Moderator/HotelAlertCommand.cs Resources/SQLs/Updates/17_HotelAlertRank5.sql
git -C emulator commit -m "feat(commands): :ha sends hotel-wide bubble notification; staff rank 5+"
```

### Task 2: Live verification (local dev)

**Files:** none (verification only).

Login mechanic: mint an SSO ticket (`docker compose exec -T db mysql -upixelrp -p"changeme-local" pixelrp -e "UPDATE users SET auth_ticket='<fresh-random>' WHERE username='<name>';"`), then open `http://localhost:8080/nitro-assets/client/index.html?sso=<ticket>` in the browser. Never type passwords.

**Steps:**

- [ ] **Step 1: Bubble broadcast.** Session A: log in as `Admin` (rank 9), stay in the landing room. Session B (second tab): log in as `ClaudeTest` (rank 1) — note ClaudeTest spawns in a different room. In session A chat: `:ha Testing hotel alerts`. Expected: BOTH sessions show a dark rounded corner bubble (class `nitro-notification-bubble`) reading exactly "Testing hotel alerts" — same format as the "Discussions in PixelRP rooms may be monitored" notice. No modal popup anywhere.
- [ ] **Step 2: Empty guard.** Session A: `:ha` with no message. Expected: whisper "Please enter a message to send.", no broadcast.
- [ ] **Step 3: Rank gate low.** Session B (`ClaudeTest`, rank 1): `:ha test`. Expected: no broadcast — the text is treated as normal chat or rejected, and session A sees no bubble.
- [ ] **Step 4: Rank gate mid.** Relog session B as `pixelrp_e2e_solo` (rank 7): `:ha Mid rank test`. Expected: bubble appears in both sessions (rank 5 gate admits rank 7, which the stock rank-8 mapping would have denied).
- [ ] **Step 5: Logs clean.** `docker compose logs emulator --tail 30` — no exceptions from the session.

### Task 3: Changelog, submodule bump, push, deploy

**Files:**
- Modify: `CHANGELOG.md`
- Modify: root submodule pointer for `emulator/`

**Steps:**

- [ ] **Step 1: Push emulator:**

```bash
git -C emulator push origin pixelrp
```

- [ ] **Step 2: Changelog.** Add a new dated section at the top of `CHANGELOG.md` (player-facing, matching existing entry style):

```markdown
## 2026-08-09 — The hotel found its tannoy

### Added

- **Hotel-wide announcements.** Staff can now broadcast a message to everyone
  online. It arrives as the small dark notification bubble in the corner —
  the same style as the moderation notice — instead of a pop-up box.
```

  (If a `## 2026-08-09` section already exists, add the `### Added` block into it instead of creating a duplicate date heading.)

- [ ] **Step 3: Bump submodule + push main:**

```bash
git add emulator CHANGELOG.md
git commit -m "chore: bump emulator (:ha hotel alert as bubble notification)"
git push
```

- [ ] **Step 4: Deploy to VPS** (pull, apply SQL 17 to prod DB, rebuild emulator):

```bash
ssh root@67.219.109.182 'cd /opt/pixelrp && git pull -q origin main && git submodule update --init emulator && git log --oneline -1'
ssh root@67.219.109.182 'cd /opt/pixelrp && source .env 2>/dev/null; docker compose -f compose.yaml -f compose.prod.yaml exec -T db mysql -upixelrp -p"$DB_PASSWORD" pixelrp < emulator/Resources/SQLs/Updates/17_HotelAlertRank5.sql'
ssh root@67.219.109.182 'cd /opt/pixelrp && docker compose -f compose.yaml -f compose.prod.yaml build emulator 2>&1 | tail -2 && docker compose -f compose.yaml -f compose.prod.yaml up -d emulator'
```

  Note: the second command reads the prod DB password from `/opt/pixelrp/.env` on the VPS (`DB_PASSWORD`); if the variable name differs there, read `.env` first and substitute. Verify boot: `docker compose -f compose.yaml -f compose.prod.yaml logs emulator --tail 10` shows `EMULATOR -> READY!`, and the prod SELECT (same as Task 1 Step 4) shows `group_id = 5`.

- [ ] **Step 5: Prod smoke test.** Log in as `Claude` (prod test account) via the prod SSO flow, and as a staff prod account if available; staff `:ha Hello hotel` → bubble appears. If no second prod staff session is practical, verify at minimum that the emulator is READY and `:ha` from a staff account produces the bubble on that same session.
