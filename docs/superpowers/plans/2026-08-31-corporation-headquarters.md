# Corporation Headquarters, Authorizations & Emergencies — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tie rooms to corporations as headquarters, gate who may work there by rank, and let rooms admit outside emergency services (Medical/Police/Staff) — making `:startwork` shifts room-permission-gated.

**Architecture:** Three repos. Emulator (`emulator/` submodule, branch `pixelrp`): a SQL migration, room-field load, four packets, and shift-gating in `ShiftManager`. The nitro-renderer yarn patch (inside `client/` submodule, branch `pixelrp`): the four packets mirrored client-side, then resealed. Client UI (`client/`): parent-held room-corp state and three extracted Roleplay pages. Spec: `docs/superpowers/specs/2026-08-31-corporation-headquarters-design.md`.

**Tech Stack:** C#/.NET 7 (PlusEMU fork, Dapper), React 18 + TypeScript + Vite (nitro-react fork), yarn Berry, Docker.

## Global Constraints

- **Submodules:** emulator edits/commits happen inside `/Users/rybealey/Documents/Personal/pixelrp/plus/emulator` (branch `pixelrp`); client + renderer-patch edits/commits inside `/Users/rybealey/Documents/Personal/pixelrp/plus/client` (branch `pixelrp`). Parent-repo pointer bumps happen only in Task 7. Do NOT push unless a task says to.
- **No local .NET SDK.** Emulator compile verification = `docker compose build emulator` from the parent repo root (`/Users/rybealey/Documents/Personal/pixelrp/plus`) succeeds. This takes a few minutes; that is normal.
- **No test infrastructure** in emulator or client. Verification per task is: it compiles/builds, plus code review. Runtime behavior is verified by the user in-game on beta after Task 7.
- **Wire/internal id rule:** every new packet gets its wire id (3957–3960) in `emulator/Resources/Revisions/1.6.6.json` (keyed by the constant NAME) and in the client renderer's `IncomingHeader`/`OutgoingHeader`. The emulator C# internal constant uses `4####` (= 40000 + wire) with a `// <wire>` comment, because stock Habbo constants occupy much of the plain 39xx range internally and a duplicate internal VALUE crash-loops the emulator at DI resolution. `439xx` is confirmed free.
- **EvaWire:** never pass a null/undefined composer field; write booleans as `1`/`0` ints, matching the existing corp packets.
- **Copy:** in-game strings use spaced hyphens, never em-dashes (pixel font renders them as a music note). CHANGELOG bullets likewise.
- **Code style:** C# — Allman braces, `_camelCase` private fields, 4-space indent, XML `///` summaries on new public types (match the zone/corp files). TS/TSX — 4-space indent, single quotes, spaces inside JSX braces.

## Wire contract (shared reference for Tasks 2, 3, 5)

All four packets, exact field order. Emulator Outgoing == client Incoming; emulator Incoming == client Outgoing.

**`RpRoomCorpComposer`** — wire **3957**, server→client (emulator ServerPacketHeader / client IncomingHeader `RP_ROOM_CORP`):
```
int    roomId
int    corpId                 // 0 = no HQ assigned
int    rankCount              // 0 when corpId == 0
  repeat rankCount: int rankId, int rankOrder, string rankName, int authorized  // 1/0
int    allowMedical           // 1/0
int    allowPolice            // 1/0
int    allowStaff             // 1/0
```
**`RpSetRoomCorpEvent`** — wire **3958**, client→server: `int corpId`.
**`RpSetHqRankEvent`** — wire **3962**, client→server: `int rankId, int authorized`. (Wire 3959 was burned — stock client `PHOTO_COMPETITION`; 3961 is `CHAT_REVIEW_GUIDE_VOTE`. 3962 verified clear.)
**`RpSetEmergencyEvent`** — wire **3960**, client→server: `int category` (0=medical,1=police,2=staff), `int enabled`.

---

### Task 1: Schema migration + room-field load (emulator)

**Files:**
- Create: `emulator/Resources/SQLs/Updates/53_CorporationHeadquarters.sql`
- Modify: `emulator/HabboHotel/Rooms/RoomData.cs` (add fields ~line 167; copy them in the `RoomData(RoomData data)` copy constructor ~line 113)
- Modify: `emulator/HabboHotel/Rooms/RoomFactory.cs` (two load sites: the object initializer ~line 55 and the `data.X = ...` block ~line 98)

**Interfaces:**
- Produces: `RoomData.CorporationId` (int), `RoomData.AllowMedical/AllowPolice/AllowStaff` (bool). `Room : RoomData` inherits them (Room.cs:26) — no Room.cs edit. Tables `rp_hq_room_ranks`, columns `rooms.corporation_id`, `rooms.allow_medical/police/staff`, `rp_corporations.service_type`.

- [ ] **Step 1: Write the migration**

Create `53_CorporationHeadquarters.sql` with exactly this content (idempotent — guarded ALTERs mirror `22_PersistModerationTickets.sql`, so it is safe under the deploy's `set -e` and re-runs):

```sql
-- pixelrp: corporation headquarters, per-rank work authorization, and
-- room emergency-service access. Room-corp link + rank allow-list + a
-- per-corp service_type tag. All ALTERs guarded (prod rooms/rp_corporations
-- predate this and the deploy runs under `set -e`).

-- rooms.corporation_id (0 = not an HQ)
SET @col := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rooms' AND COLUMN_NAME = 'corporation_id');
SET @sql := IF(@col = 0,
  'ALTER TABLE `rooms` ADD COLUMN `corporation_id` INT NOT NULL DEFAULT 0',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- rooms.allow_medical / allow_police / allow_staff (emergency access, default on)
SET @col := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rooms' AND COLUMN_NAME = 'allow_medical');
SET @sql := IF(@col = 0,
  'ALTER TABLE `rooms` ADD COLUMN `allow_medical` ENUM(''0'',''1'') NOT NULL DEFAULT ''1''',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @col := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rooms' AND COLUMN_NAME = 'allow_police');
SET @sql := IF(@col = 0,
  'ALTER TABLE `rooms` ADD COLUMN `allow_police` ENUM(''0'',''1'') NOT NULL DEFAULT ''1''',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @col := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rooms' AND COLUMN_NAME = 'allow_staff');
SET @sql := IF(@col = 0,
  'ALTER TABLE `rooms` ADD COLUMN `allow_staff` ENUM(''0'',''1'') NOT NULL DEFAULT ''1''',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- rp_corporations.service_type ('', 'medical', 'police', 'staff')
SET @col := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rp_corporations' AND COLUMN_NAME = 'service_type');
SET @sql := IF(@col = 0,
  'ALTER TABLE `rp_corporations` ADD COLUMN `service_type` VARCHAR(12) NOT NULL DEFAULT ''''',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Seed service tags by acronym (idempotent).
UPDATE `rp_corporations` SET `service_type` = 'medical' WHERE `acronym` = 'HMMC';
UPDATE `rp_corporations` SET `service_type` = 'police'  WHERE `acronym` = 'SFPD';
UPDATE `rp_corporations` SET `service_type` = 'staff'   WHERE `acronym` = 'PRPL';

-- Per-room authorized ranks (a row = that rank may work in that room).
CREATE TABLE IF NOT EXISTS `rp_hq_room_ranks` (
  `room_id` INT NOT NULL,
  `rank_id` INT NOT NULL,
  PRIMARY KEY (`room_id`, `rank_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Add the fields to RoomData**

In `emulator/HabboHotel/Rooms/RoomData.cs`, next to `public bool IsSafeZone { get; set; }` (line 167), add:

```csharp
    // pixelrp: the corporation this room is the headquarters of (0 = none).
    // RoomFactory assigns it after construction from `corporation_id`.
    public int CorporationId { get; set; }

    // pixelrp: which outside emergency services may work in this room.
    // Default on; assigned by RoomFactory from allow_medical/police/staff.
    public bool AllowMedical { get; set; }
    public bool AllowPolice { get; set; }
    public bool AllowStaff { get; set; }
```

In the same file's copy constructor (near `IsSafeZone = data.IsSafeZone;` at line 113), add:

```csharp
        CorporationId = data.CorporationId;
        AllowMedical = data.AllowMedical;
        AllowPolice = data.AllowPolice;
        AllowStaff = data.AllowStaff;
```

- [ ] **Step 3: Load the columns in RoomFactory**

In `emulator/HabboHotel/Rooms/RoomFactory.cs`, at the object-initializer site (~line 55, alongside `IsSafeZone = ToBool(row["is_safe_zone"])`), add:

```csharp
                        CorporationId = Convert.ToInt32(row["corporation_id"]),
                        AllowMedical = ToBool(row["allow_medical"]),
                        AllowPolice = ToBool(row["allow_police"]),
                        AllowStaff = ToBool(row["allow_staff"]),
```

At the second site (~line 98, alongside `data.IsSafeZone = ToBool(row["is_safe_zone"]);`), add:

```csharp
                data.CorporationId = Convert.ToInt32(row["corporation_id"]);
                data.AllowMedical = ToBool(row["allow_medical"]);
                data.AllowPolice = ToBool(row["allow_police"]);
                data.AllowStaff = ToBool(row["allow_staff"]);
```

(Match the exact comma/semicolon style of the surrounding lines at each site. If `Convert` isn't already imported, it is `System.Convert` — the file already uses `ToBool`, and likely `Convert` elsewhere; add `using System;` only if the build says it's missing.)

- [ ] **Step 4: Compile**

Run from `/Users/rybealey/Documents/Personal/pixelrp/plus`: `docker compose build emulator`
Expected: build completes (the `dotnet publish` stage succeeds).

- [ ] **Step 5: Commit (inside the emulator submodule)**

```bash
cd emulator
git add "Resources/SQLs/Updates/53_CorporationHeadquarters.sql" HabboHotel/Rooms/RoomData.cs HabboHotel/Rooms/RoomFactory.cs
git commit -m "feat(corps): room HQ, rank-auth and emergency schema + room load

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Read-path packet — headers, composer, settings-open send (emulator)

**Files:**
- Modify: `emulator/Communication/Packets/Outgoing/ServerPacketHeader.cs` (add `RpRoomCorpComposer`)
- Modify: `emulator/Communication/Packets/Incoming/ClientPacketHeader.cs` (add the 3 event consts)
- Modify: `emulator/Resources/Revisions/1.6.6.json` (4 entries: 1 in the outgoing map, 3 in the incoming map)
- Create: `emulator/Communication/Packets/Outgoing/Rooms/Settings/RpRoomCorpComposer.cs`
- Modify: `emulator/HabboHotel/Corporations/CorporationUtility.cs` (add `BuildRoomCorp`)
- Modify: `emulator/Communication/Packets/Incoming/Rooms/Settings/GetRoomSettingsEvent.cs` (send after the zone composer, ~line 27)

**Interfaces:**
- Consumes: `Room.CorporationId/AllowMedical/AllowPolice/AllowStaff` (Task 1).
- Produces: `RpRoomCorpComposer` (built via `CorporationUtility.BuildRoomCorp(Room room)` → `RpRoomCorpComposer`), and the four header constants. Task 3's write handlers reuse `BuildRoomCorp` to echo; Task 3's events reference the `ClientPacketHeader` constants added here.

- [ ] **Step 1: Add the header constants**

In `ServerPacketHeader.cs`, near `RpRoomZoneComposer = 3924;`, add:

```csharp
    public const uint RpRoomCorpComposer = 43957; //3957
```

In `ClientPacketHeader.cs`, near `RpRoomZoneSaveEvent = 3923;`, add:

```csharp
    public const uint RpSetRoomCorpEvent = 43958; //3958
    public const uint RpSetHqRankEvent = 43962; //3962
    public const uint RpSetEmergencyEvent = 43960; //3960
```

- [ ] **Step 2: Add the wire ids to the revision map**

In `emulator/Resources/Revisions/1.6.6.json`: in the **outgoing** map (where `"RpRoomZoneComposer": 3924` lives, ~line 591) add `"RpRoomCorpComposer": 3957,`. In the **incoming** map (where `"RpRoomZoneSaveEvent": 3923` lives, ~line 303) add `"RpSetRoomCorpEvent": 3958,`, `"RpSetHqRankEvent": 3962,`, `"RpSetEmergencyEvent": 3960,`. Keep valid JSON (commas, no trailing comma at a map's end).

- [ ] **Step 3: Write the composer**

Create `RpRoomCorpComposer.cs`. It takes a prepared data shape and writes the wire contract:

```csharp
using System.Collections.Generic;

namespace Plus.Communication.Packets.Outgoing.Rooms.Settings;

/// <summary>
/// pixelrp: a room's roleplay-corp config for Room settings > Roleplay:
/// its headquarters corporation, that corp's ranks with per-rank work
/// authorization, and the room's emergency-service access flags. Sent
/// alongside RoomSettingsDataComposer when the window opens, and echoed
/// after every RpSetRoomCorp / RpSetHqRank / RpSetEmergency write.
/// </summary>
public class RpRoomCorpComposer : IServerPacket
{
    public readonly record struct RankRow(int RankId, int RankOrder, string RankName, bool Authorized);

    private readonly int _roomId;
    private readonly int _corpId;
    private readonly IReadOnlyList<RankRow> _ranks;
    private readonly bool _allowMedical;
    private readonly bool _allowPolice;
    private readonly bool _allowStaff;

    public uint MessageId => ServerPacketHeader.RpRoomCorpComposer;

    public RpRoomCorpComposer(int roomId, int corpId, IReadOnlyList<RankRow> ranks,
        bool allowMedical, bool allowPolice, bool allowStaff)
    {
        _roomId = roomId;
        _corpId = corpId;
        _ranks = ranks ?? new List<RankRow>();
        _allowMedical = allowMedical;
        _allowPolice = allowPolice;
        _allowStaff = allowStaff;
    }

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteInteger(_roomId);
        packet.WriteInteger(_corpId);
        packet.WriteInteger(_ranks.Count);
        foreach (var rank in _ranks)
        {
            packet.WriteInteger(rank.RankId);
            packet.WriteInteger(rank.RankOrder);
            packet.WriteString(rank.RankName);
            packet.WriteInteger(rank.Authorized ? 1 : 0);
        }
        packet.WriteInteger(_allowMedical ? 1 : 0);
        packet.WriteInteger(_allowPolice ? 1 : 0);
        packet.WriteInteger(_allowStaff ? 1 : 0);
    }
}
```

(Confirm the packet-writer method names against `RpRoomZoneComposer.cs`/`RpUserCorpComposer.cs` — it uses `WriteInteger`, `WriteString`, `WriteBoolean`. Use `WriteInteger(... ? 1 : 0)` for the flags as above, matching how the corp packets send booleans as ints.)

- [ ] **Step 4: Add the `BuildRoomCorp` helper**

In `emulator/HabboHotel/Corporations/CorporationUtility.cs`, add a static method that reads the room's flags and, when the room has an HQ corp, that corp's ranks joined to the authorization table. Use the Dapper/`PlusEnvironment.DatabaseManager.Connection()` style already in this file:

```csharp
    // pixelrp: assembles the RpRoomCorpComposer for a room - its HQ corp's
    // ranks with per-rank authorization plus the room's emergency flags.
    public static RpRoomCorpComposer BuildRoomCorp(Room room)
    {
        var ranks = new List<RpRoomCorpComposer.RankRow>();
        if (room.CorporationId > 0)
        {
            using var connection = PlusEnvironment.DatabaseManager.Connection();
            var rows = connection.Query<(int Id, int RankOrder, string Name, int Authorized)>(
                "SELECT r.`id` AS Id, r.`rank_order` AS RankOrder, r.`name` AS Name, " +
                "(a.`rank_id` IS NOT NULL) AS Authorized " +
                "FROM `rp_corporation_ranks` r " +
                "LEFT JOIN `rp_hq_room_ranks` a ON a.`rank_id` = r.`id` AND a.`room_id` = @roomId " +
                "WHERE r.`corporation_id` = @corpId ORDER BY r.`rank_order`",
                new { roomId = room.Id, corpId = room.CorporationId });
            foreach (var row in rows)
                ranks.Add(new RpRoomCorpComposer.RankRow(row.Id, row.RankOrder, row.Name, row.Authorized == 1));
        }
        return new RpRoomCorpComposer((int)room.Id, room.CorporationId, ranks,
            room.AllowMedical, room.AllowPolice, room.AllowStaff);
    }
```

Add the needed `using` lines to `CorporationUtility.cs` if missing: `using System.Collections.Generic;`, `using Dapper;`, `using Plus.Communication.Packets.Outgoing.Rooms.Settings;`, `using Plus.HabboHotel.Rooms;`. (`room.Id` may be `uint`; cast to `int` as shown.)

- [ ] **Step 5: Send it when the settings window opens**

In `emulator/Communication/Packets/Incoming/Rooms/Settings/GetRoomSettingsEvent.cs`, immediately after the existing `session.Send(new RpRoomZoneComposer(room.Id, room.IsSafeZone));` (line 27), add:

```csharp
        session.Send(Plus.HabboHotel.Corporations.CorporationUtility.BuildRoomCorp(room));
```

(Or add a `using Plus.HabboHotel.Corporations;` and call `CorporationUtility.BuildRoomCorp(room)`. Match the file's existing using style.)

- [ ] **Step 6: Compile**

`docker compose build emulator` from the parent root. Expected: success.

- [ ] **Step 7: Commit (emulator submodule)**

```bash
cd emulator
git add Communication/Packets/Outgoing/ServerPacketHeader.cs Communication/Packets/Incoming/ClientPacketHeader.cs Resources/Revisions/1.6.6.json Communication/Packets/Outgoing/Rooms/Settings/RpRoomCorpComposer.cs HabboHotel/Corporations/CorporationUtility.cs Communication/Packets/Incoming/Rooms/Settings/GetRoomSettingsEvent.cs
git commit -m "feat(corps): RpRoomCorpComposer + room-settings send (read path)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Write-path packets — set HQ, toggle rank, toggle emergency (emulator)

**Files:**
- Create: `emulator/Communication/Packets/Incoming/Rooms/Settings/RpSetRoomCorpEvent.cs`
- Create: `emulator/Communication/Packets/Incoming/Rooms/Settings/RpSetHqRankEvent.cs`
- Create: `emulator/Communication/Packets/Incoming/Rooms/Settings/RpSetEmergencyEvent.cs`

**Interfaces:**
- Consumes: `CorporationUtility.BuildRoomCorp` (Task 2), `ClientPacketHeader.RpSetRoomCorpEvent/RpSetHqRankEvent/RpSetEmergencyEvent` (Task 2), `Room.CorporationId/AllowMedical/AllowPolice/AllowStaff` (Task 1). Auto-registered by `PacketManager` reflection (class name == header const name).
- Produces: nothing consumed later (Task 4's gating reads the tables directly).

- [ ] **Step 1: Write `RpSetRoomCorpEvent` (staff + rights; set/clear + reseed)**

```csharp
using Dapper;
using Plus.HabboHotel.Corporations;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Rooms.Settings;

/// <summary>
/// pixelrp: assigns (or clears, corpId 0) this room as a corporation's
/// headquarters. Staff only. On assign, seeds all of the corp's ranks as
/// authorized; on clear/reassign, drops the room's rank rows first.
/// </summary>
internal class RpSetRoomCorpEvent : IPacketEvent
{
    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        var corpId = packet.ReadInt();
        var room = session.GetHabbo()?.CurrentRoom;
        if (room == null) return Task.CompletedTask;
        if (!room.CheckRights(session, true)) return Task.CompletedTask;
        if (session.GetHabbo().Rank < 5) return Task.CompletedTask;

        using (var connection = PlusEnvironment.DatabaseManager.Connection())
        {
            // Validate the corp exists (or 0 to clear).
            if (corpId > 0)
            {
                var exists = connection.QuerySingleOrDefault<int?>(
                    "SELECT `id` FROM `rp_corporations` WHERE `id` = @corpId LIMIT 1", new { corpId });
                if (exists == null) corpId = 0;
            }
            connection.Execute("UPDATE `rooms` SET `corporation_id` = @corpId WHERE `id` = @roomId LIMIT 1",
                new { corpId, roomId = room.Id });
            connection.Execute("DELETE FROM `rp_hq_room_ranks` WHERE `room_id` = @roomId", new { roomId = room.Id });
            if (corpId > 0)
                connection.Execute(
                    "INSERT INTO `rp_hq_room_ranks` (`room_id`, `rank_id`) " +
                    "SELECT @roomId, `id` FROM `rp_corporation_ranks` WHERE `corporation_id` = @corpId",
                    new { roomId = room.Id, corpId });
        }
        room.CorporationId = corpId;
        session.Send(CorporationUtility.BuildRoomCorp(room));
        return Task.CompletedTask;
    }
}
```

- [ ] **Step 2: Write `RpSetHqRankEvent` (staff + rights; toggle one rank)**

```csharp
using Dapper;
using Plus.HabboHotel.Corporations;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Rooms.Settings;

/// <summary>
/// pixelrp: toggles whether one rank may work in this room's headquarters.
/// Staff only; the rank must belong to the room's assigned corporation.
/// </summary>
internal class RpSetHqRankEvent : IPacketEvent
{
    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        var rankId = packet.ReadInt();
        var authorized = packet.ReadInt() == 1;
        var room = session.GetHabbo()?.CurrentRoom;
        if (room == null) return Task.CompletedTask;
        if (!room.CheckRights(session, true)) return Task.CompletedTask;
        if (session.GetHabbo().Rank < 5) return Task.CompletedTask;
        if (room.CorporationId <= 0) return Task.CompletedTask;

        using (var connection = PlusEnvironment.DatabaseManager.Connection())
        {
            // Rank must belong to this room's corp.
            var ok = connection.QuerySingleOrDefault<int?>(
                "SELECT `id` FROM `rp_corporation_ranks` WHERE `id` = @rankId AND `corporation_id` = @corpId LIMIT 1",
                new { rankId, corpId = room.CorporationId });
            if (ok == null) return Task.CompletedTask;
            if (authorized)
                connection.Execute("INSERT IGNORE INTO `rp_hq_room_ranks` (`room_id`, `rank_id`) VALUES (@roomId, @rankId)",
                    new { roomId = room.Id, rankId });
            else
                connection.Execute("DELETE FROM `rp_hq_room_ranks` WHERE `room_id` = @roomId AND `rank_id` = @rankId",
                    new { roomId = room.Id, rankId });
        }
        session.Send(CorporationUtility.BuildRoomCorp(room));
        return Task.CompletedTask;
    }
}
```

- [ ] **Step 3: Write `RpSetEmergencyEvent` (owner OR staff; toggle a room flag)**

```csharp
using Dapper;
using Plus.HabboHotel.Corporations;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Rooms.Settings;

/// <summary>
/// pixelrp: toggles which outside emergency service (0 medical, 1 police,
/// 2 staff) may work in this room. Editable by the room owner or staff
/// (CheckRights), unlike the staff-only HQ settings.
/// </summary>
internal class RpSetEmergencyEvent : IPacketEvent
{
    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        var category = packet.ReadInt();
        var enabled = packet.ReadInt() == 1;
        var room = session.GetHabbo()?.CurrentRoom;
        if (room == null) return Task.CompletedTask;
        if (!room.CheckRights(session, true)) return Task.CompletedTask;

        string column;
        switch (category)
        {
            case 0: column = "allow_medical"; room.AllowMedical = enabled; break;
            case 1: column = "allow_police"; room.AllowPolice = enabled; break;
            case 2: column = "allow_staff"; room.AllowStaff = enabled; break;
            default: return Task.CompletedTask;
        }
        using (var connection = PlusEnvironment.DatabaseManager.Connection())
        {
            connection.Execute($"UPDATE `rooms` SET `{column}` = @val WHERE `id` = @roomId LIMIT 1",
                new { val = enabled ? "1" : "0", roomId = room.Id });
        }
        session.Send(CorporationUtility.BuildRoomCorp(room));
        return Task.CompletedTask;
    }
}
```

(`column` is chosen from a fixed switch, never from packet data — no injection surface.)

- [ ] **Step 4: Compile**

`docker compose build emulator`. Expected: success. (If the build complains the `IIncomingPacket.ReadInt`/`IPacketEvent` shape differs, match `RpRoomZoneSaveEvent.cs` exactly — it is the canonical template for these three.)

- [ ] **Step 5: Commit (emulator submodule)**

```bash
cd emulator
git add Communication/Packets/Incoming/Rooms/Settings/RpSetRoomCorpEvent.cs Communication/Packets/Incoming/Rooms/Settings/RpSetHqRankEvent.cs Communication/Packets/Incoming/Rooms/Settings/RpSetEmergencyEvent.cs
git commit -m "feat(corps): RpSetRoomCorp / RpSetHqRank / RpSetEmergency write handlers

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Shift work-gating + continuous enforcement (emulator)

**Files:**
- Modify: `emulator/HabboHotel/Corporations/CorporationUtility.cs` (add `EvaluateWork`)
- Modify: `emulator/HabboHotel/Corporations/ShiftManager.cs` (gate `StartShift`; store gating fields on `ShiftSession`; enforce in `TickSession`; add `InterruptForLeftWork`)

**Interfaces:**
- Consumes: `Room.CorporationId/AllowMedical/AllowPolice/AllowStaff` (Task 1); the `rp_hq_room_ranks` table and `rp_corporations.service_type` (Task 1).
- Produces: `CorporationUtility.EvaluateWork(Habbo) -> (bool Ok, string Reason)`.

- [ ] **Step 1: Add `EvaluateWork` to CorporationUtility**

```csharp
    // pixelrp: may this employee be on the clock in the room they're
    // standing in right now? A corp with no HQ works anywhere (unchanged).
    // Otherwise: their HQ room with an authorized rank, OR a room that
    // admits their corp's emergency service. Reason is whisper-ready.
    public static (bool Ok, string Reason) EvaluateWork(Habbo habbo)
    {
        var room = habbo?.CurrentRoom;
        using var connection = PlusEnvironment.DatabaseManager.Connection();
        var job = connection.QuerySingleOrDefault<(int CorpId, int RankId, string ServiceType)?>(
            "SELECT e.`corporation_id` AS CorpId, e.`rank_id` AS RankId, c.`service_type` AS ServiceType " +
            "FROM `rp_corporation_employees` e " +
            "INNER JOIN `rp_corporations` c ON c.`id` = e.`corporation_id` " +
            "WHERE e.`user_id` = @userId LIMIT 1", new { userId = habbo.Id });
        if (job == null) return (false, "You don't have a job. Get hired by a corporation first.");

        var hqCount = connection.QuerySingle<int>(
            "SELECT COUNT(*) FROM `rooms` WHERE `corporation_id` = @corpId", new { corpId = job.Value.CorpId });
        if (hqCount == 0) return (true, "");           // no HQ anywhere -> work anywhere

        if (room == null) return (false, "You can only work at your headquarters or an approved location.");

        // At their own HQ: rank must be authorized.
        if (room.CorporationId == job.Value.CorpId)
        {
            var authorized = connection.QuerySingleOrDefault<int?>(
                "SELECT 1 FROM `rp_hq_room_ranks` WHERE `room_id` = @roomId AND `rank_id` = @rankId LIMIT 1",
                new { roomId = room.Id, rankId = job.Value.RankId });
            if (authorized != null) return (true, "");
            return (false, "Your rank isn't cleared to work here.");
        }

        // Emergency service access to this room.
        var svc = job.Value.ServiceType;
        if ((svc == "medical" && room.AllowMedical) ||
            (svc == "police" && room.AllowPolice) ||
            (svc == "staff" && room.AllowStaff))
            return (true, "");

        return (false, "You can only work at your headquarters or an approved location.");
    }
```

Ensure `using Plus.HabboHotel.Users;` is present for `Habbo` (it likely is).

- [ ] **Step 2: Gate `StartShift`**

In `ShiftManager.StartShift`, after the `if (Sessions.ContainsKey(userId))` early-return block and BEFORE the job query / `on_duty = 1` write, add:

```csharp
        var permit = CorporationUtility.EvaluateWork(client.GetHabbo());
        if (!permit.Ok)
        {
            client.SendWhisper(permit.Reason);
            return;
        }
```

(`EvaluateWork` already returns the "no job" reason, so this also covers the unemployed case; the existing `job == null` whisper below remains as a defensive fallback.)

- [ ] **Step 3: Record gating fields on the session**

In the `ShiftSession` class, add fields:

```csharp
        // pixelrp: gating context so the minute tick can re-check permission
        // without another employment lookup. HqGated == corp has >=1 HQ room.
        public int CorpId;
        public int RankId;
        public bool HqGated;
```

In `StartShift`, when building the `ShiftSession`, set them. Extend the existing job query to also select `e.corporation_id`, `e.rank_id`, and whether the corp has an HQ — OR (simpler, one extra query) set them from a small lookup right after the session is created:

```csharp
        session.CorpId = /* e.corporation_id from the job query */;
        session.RankId = /* e.rank_id from the job query */;
        session.HqGated = /* SELECT COUNT(*)>0 FROM rooms WHERE corporation_id = session.CorpId */;
```

Prefer extending the existing `job` SELECT in `StartShift` to include `e.corporation_id AS CorpId, e.rank_id AS RankId` (add to the tuple type and the SQL), and run one `COUNT(*)` for `HqGated`, to avoid a redundant employment round-trip. Keep the tuple change local to `StartShift`.

- [ ] **Step 4: Enforce in `TickSession`**

In `TickSession`, inside the `lock (session)` block, after the existing `CurrentRoom == null` handling and before the payout drain, add a permission re-check for HQ-gated sessions:

```csharp
            if (session.HqGated)
            {
                var permit = CorporationUtility.EvaluateWork(client.GetHabbo());
                if (!permit.Ok)
                {
                    Sessions.TryRemove(session.UserId, out _);
                    EndSession(session, client);
                    RevertMotto(client);
                    InterruptForLeftWork(client);
                    return;
                }
            }
```

(This sits after the room-less branch, so a genuinely room-less HQ-gated worker is caught here too — `EvaluateWork` returns false when `CurrentRoom == null` — which is fine; the two-minute grace only applies to non-gated workers. Order it AFTER the `NoRoomMinutes` block and BEFORE `DrainCompletedIntervals`.)

- [ ] **Step 5: Add `InterruptForLeftWork`**

Mirror the shout style of `InterruptForIdle` (which shouts `*has fallen asleep on duty*` via `AnnounceShift`). Add:

```csharp
    // pixelrp: a room shout when an HQ-gated worker is clocked out for no
    // longer being in a room they may work in (left the workplace, rank
    // deauthorized mid-shift, or the room's HQ was reassigned).
    private static void InterruptForLeftWork(GameClient client)
    {
        AnnounceShift(client, "*has clocked out - left the workplace*");
    }
```

(`EndSession` + `RevertMotto` are already called in Step 4 before this, matching how `InterruptForIdle` orders its teardown; verify against `InterruptForIdle`'s body and mirror the exact call order — do not double-remove the session.)

- [ ] **Step 6: Compile**

`docker compose build emulator`. Expected: success.

- [ ] **Step 7: Commit (emulator submodule)**

```bash
cd emulator
git add HabboHotel/Corporations/CorporationUtility.cs HabboHotel/Corporations/ShiftManager.cs
git commit -m "feat(corps): gate shifts to authorized HQ / emergency rooms + tick enforcement

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Renderer-patch packets (client submodule)

**Files (inside the patched `@nitrots/nitro-renderer`, under `client/node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/`):**
- Create: `incoming/RpRoomCorpEvent.ts`
- Create: `outgoing/RpSetRoomCorpComposer.ts`, `outgoing/RpSetHqRankComposer.ts`, `outgoing/RpSetEmergencyComposer.ts`
- Modify: `incoming/index.ts`, `outgoing/index.ts` (barrel exports)
- Modify: `incoming/IncomingHeader.ts`, `outgoing/OutgoingHeader.ts` (header consts)
- Modify: `NitroMessages.ts` (register)
- Then reseal: produces changed `client/package.json`, `client/yarn.lock`, `client/.yarn/patches/*`

**Interfaces:**
- Consumes: the wire contract (top of plan) — client Incoming `RP_ROOM_CORP = 3957`; client Outgoing `RP_SET_ROOM_CORP = 3958`, `RP_SET_HQ_RANK = 3962`, `RP_SET_EMERGENCY = 3960`.
- Produces (client `@nitrots/nitro-renderer` exports for Task 6): `RpRoomCorpEvent` (+ parser getters `roomId, corpId, ranks: RpRoomCorpRank[], allowMedical, allowPolice, allowStaff`), `RpSetRoomCorpComposer(corpId)`, `RpSetHqRankComposer(rankId, authorized)`, `RpSetEmergencyComposer(category, enabled)`.

- [ ] **Step 1: Open the patch for editing**

From `client/`, run `yarn patch -u @nitrots/nitro-renderer`. If it errors "ambiguous", re-run with the full FINAL descriptor it lists (the newest one, ending in the newest `.patch` file + `&hash=`), quoted. Note the temp extract dir it prints. **Gate:** before editing, confirm the extract has our customs, not a pristine copy — `grep -rl "RpRoomZoneEvent\|RP_ROOM_ZONE" <extractDir>/src/nitro/communication/messages/` must hit. If it returns nothing, you extracted pristine — stop and re-run with the correct descriptor.

- [ ] **Step 2: Create the incoming event**

`incoming/RpRoomCorpEvent.ts` — mirror the structure of the existing `incoming/RpRoomZoneEvent.ts` and `incoming/RpCorpDetailEvent.ts` (which reads a rank loop). Parser reads the wire contract exactly:

```ts
import { IMessageEvent } from '../../../../../core';
import { MessageEvent } from '../../../../../core/communication/messages/MessageEvent';
import { RpRoomCorpParser } from '../parser';   // match how RpRoomZoneEvent imports its parser

export class RpRoomCorpEvent extends MessageEvent
{
    constructor(callBack: Function)
    {
        super(callBack, RpRoomCorpParser);
    }

    public getParser(): RpRoomCorpParser
    {
        return this.parser as RpRoomCorpParser;
    }
}
```

And the parser (place it exactly where `RpRoomZoneParser` lives — mirror that file's location and import path; the exploration found parsers colocated). Parser reads:
```
roomId = readInt(); corpId = readInt(); rankCount = readInt();
ranks = []; for rankCount: { rankId=readInt, rankOrder=readInt, rankName=readString, authorized: readInt===1 }
allowMedical = readInt()===1; allowPolice = readInt()===1; allowStaff = readInt()===1;
```
with getters `roomId, corpId, ranks (RpRoomCorpRank[]), allowMedical, allowPolice, allowStaff`, and an exported interface `RpRoomCorpRank { rankId: number; rankOrder: number; rankName: string; authorized: boolean }`. **Copy the exact class/parser/interface skeleton and import paths from `RpRoomZoneEvent.ts` + its parser and from `RpCorpDetailEvent.ts` (for the rank-loop idiom) — those are the ground truth for this repo's conventions.**

- [ ] **Step 3: Create the three outgoing composers**

Mirror `outgoing/RpRoomZoneSaveComposer.ts` (a one-field composer). Each:

```ts
// RpSetRoomCorpComposer.ts
import { IMessageComposer } from '../../../../../core';
export class RpSetRoomCorpComposer implements IMessageComposer<ConstructorParameters<typeof RpSetRoomCorpComposer>>
{
    private _data: ConstructorParameters<typeof RpSetRoomCorpComposer>;
    constructor(corpId: number) { this._data = [ corpId ]; }
    public getMessageArray() { return this._data; }
    public dispose(): void { return; }
}
```
`RpSetHqRankComposer(rankId: number, authorized: boolean)` → `this._data = [ rankId, authorized ? 1 : 0 ]`. `RpSetEmergencyComposer(category: number, enabled: boolean)` → `this._data = [ category, enabled ? 1 : 0 ]`. **Match `RpRoomZoneSaveComposer.ts`'s exact import path and shape** (it may differ slightly from the skeleton above — copy the real file).

- [ ] **Step 4: Barrels + headers + registration**

- `incoming/index.ts`: `export *` the new event (and parser file if separate), beside the RpRoomZone lines.
- `outgoing/index.ts`: `export *` the three composers.
- `incoming/IncomingHeader.ts`: `public static readonly RP_ROOM_CORP: number = 3957;` (match the file's declaration style, near `RP_ROOM_ZONE`).
- `outgoing/OutgoingHeader.ts`: `RP_SET_ROOM_CORP = 3958`, `RP_SET_HQ_RANK = 3962`, `RP_SET_EMERGENCY = 3960` (match style near `RP_ROOM_ZONE_SAVE`).
- `NitroMessages.ts`: import the four classes; `this._events.set(IncomingHeader.RP_ROOM_CORP, RpRoomCorpEvent);` beside the RP_ROOM_ZONE registration; `this._composers.set(OutgoingHeader.RP_SET_ROOM_CORP, RpSetRoomCorpComposer);` and the other two beside RP_ROOM_ZONE_SAVE.

- [ ] **Step 5: Reseal the patch**

From `client/`: `yarn patch-commit -s <extractDir>` (creates a new stacked patch), then `yarn install`. Verify BOTH old and new symbols survive:
```bash
grep -rl "RP_ROOM_ZONE\b" node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/incoming/IncomingHeader.ts   # old survives
grep -rl "RP_ROOM_CORP" node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/incoming/IncomingHeader.ts     # new present
grep -rl "RpSetEmergencyComposer" node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/outgoing/           # new present
```
All three must print a path. (If the reseal dropped customs, you resealed a pristine extract — the reseal trap; redo from Step 1.)

- [ ] **Step 6: Build the client**

From `client/`: `yarn build`. Expected: success (this compiles the app against the resealed renderer; a bad export or header surfaces here).

- [ ] **Step 7: Commit (client submodule)**

```bash
cd client
git add package.json yarn.lock .yarn/patches
git commit -m "feat(corps): renderer packets for room HQ / rank-auth / emergency

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Roleplay pages UI (client)

**Files:**
- Modify: `client/src/components/navigator/views/room-settings/NavigatorRoomSettingsView.tsx` (hoist room-corp state; pass to the tab; listen for `RpRoomCorpEvent`)
- Modify: `client/src/components/navigator/views/room-settings/NavigatorRoomSettingsRoleplayTabView.tsx` (route to the three page components; accept the new props)
- Create: `client/src/components/navigator/views/room-settings/RoleplayHeadquartersView.tsx`
- Create: `client/src/components/navigator/views/room-settings/RoleplayAuthorizationsView.tsx`
- Create: `client/src/components/navigator/views/room-settings/RoleplayEmergenciesView.tsx`

**Interfaces:**
- Consumes: `RpRoomCorpEvent`, `RpCorpsEvent`, `RpGetCorpsComposer`, `RpSetRoomCorpComposer`, `RpSetHqRankComposer`, `RpSetEmergencyComposer` from `@nitrots/nitro-renderer` (Task 5); `IsRpStaff` from the api/session layer; `SendMessageComposer`, `useMessageEvent`.
- Produces: nothing downstream.

- [ ] **Step 1: Define a shared room-corp shape and hoist state in the parent**

In `NavigatorRoomSettingsView.tsx`, add state mirroring `isSafeZone`. Define a local type and a `useMessageEvent<RpRoomCorpEvent>` handler that stores the parsed config:

```tsx
interface RoomCorpState
{
    corpId: number;
    ranks: { rankId: number; rankOrder: number; rankName: string; authorized: boolean }[];
    allowMedical: boolean;
    allowPolice: boolean;
    allowStaff: boolean;
}
```
```tsx
    const [ roomCorp, setRoomCorp ] = useState<RoomCorpState>(null);

    useMessageEvent<RpRoomCorpEvent>(RpRoomCorpEvent, event =>
    {
        const parser = event.getParser();
        if(!parser) return;
        setRoomCorp({
            corpId: parser.corpId,
            ranks: parser.ranks.map(r => ({ rankId: r.rankId, rankOrder: r.rankOrder, rankName: r.rankName, authorized: r.authorized })),
            allowMedical: parser.allowMedical,
            allowPolice: parser.allowPolice,
            allowStaff: parser.allowStaff
        });
    });
```
Reset `roomCorp` to `null` in `onClose` (beside the existing resets). Pass `roomCorp` and `setRoomCorp` into `NavigatorRoomSettingsRoleplayTabView` (extend its props alongside `isSafeZone`/`setIsSafeZone`). Add the import for `RpRoomCorpEvent`.

- [ ] **Step 2: Route the three pages in the tab view**

In `NavigatorRoomSettingsRoleplayTabView.tsx`, extend the props interface with `roomCorp: RoomCorpState` and `setRoomCorp: (v: RoomCorpState) => void` (import/redefine the type; simplest is to export `RoomCorpState` from the parent and import it here). Replace the placeholder branch for the three Corporation pages with the extracted components:

```tsx
            { (activePage === 'Zoning') &&
                <Column gap={ 1 } className="prp-subnav-page">
                    { /* existing zoning content unchanged */ }
                </Column> }
            { (activePage === 'Headquarters') &&
                <RoleplayHeadquartersView roomCorp={ roomCorp } className="prp-subnav-page" /> }
            { (activePage === 'Authorizations') &&
                <RoleplayAuthorizationsView roomCorp={ roomCorp } className="prp-subnav-page" /> }
            { (activePage === 'Emergencies') &&
                <RoleplayEmergenciesView roomCorp={ roomCorp } className="prp-subnav-page" /> }
```
Keep the `Zoning`/`Emergencies` list entries as they are; the placeholder fallback (`activePage !== 'Zoning'`) is now replaced by explicit branches, so remove the old generic placeholder block. (There is no longer any page without a branch — every entry in `GENERAL_PAGES`/`CORPORATION_PAGES` now has one.)

- [ ] **Step 3: `RoleplayHeadquartersView`**

On mount, request the corp list; render a `<select>` of `None` + all corps; current value = `roomCorp?.corpId`; on change send `RpSetRoomCorpComposer`. Staff-only editable via `IsRpStaff()`:

```tsx
import { RpCorpsEvent, RpGetCorpsComposer, RpSetRoomCorpComposer } from '@nitrots/nitro-renderer';
import { FC, useEffect, useState } from 'react';
import { IsRpStaff, SendMessageComposer } from '../../../../api';
import { Column, Text } from '../../../../common';
import { useMessageEvent } from '../../../../hooks';

interface Props { roomCorp: { corpId: number } | null; className?: string; }

export const RoleplayHeadquartersView: FC<Props> = ({ roomCorp = null, className = '' }) =>
{
    const [ corps, setCorps ] = useState<{ id: number; name: string }[]>([]);
    const staff = IsRpStaff();

    useMessageEvent<RpCorpsEvent>(RpCorpsEvent, event =>
    {
        const parser = event.getParser();
        if(!parser) return;
        setCorps(parser.corps.map(c => ({ id: c.id, name: c.name })));
    });

    useEffect(() => { SendMessageComposer(new RpGetCorpsComposer()); }, []);

    const onChange = (value: string) => SendMessageComposer(new RpSetRoomCorpComposer(parseInt(value)));

    return (
        <Column gap={ 1 } className={ className }>
            <Text bold>Headquarters</Text>
            <Text>Assign this room as a corporation's headquarters. Its employees can then work here.</Text>
            <select className="form-select form-select-sm" disabled={ !staff }
                value={ roomCorp ? roomCorp.corpId : 0 } onChange={ event => onChange(event.target.value) }>
                <option value={ 0 }>None</option>
                { corps.map(corp => (
                    <option key={ corp.id } value={ corp.id }>{ corp.name }</option>
                )) }
            </select>
            { !staff && <Text small className="text-muted">Only staff can set a headquarters.</Text> }
        </Column>
    );
}
```
Verify `RpCorpsEvent` parser exposes `corps` with `id`/`name` (the exploration confirmed `{ id, name, badge, employees }`). Verify `IsRpStaff` import path against an existing consumer (the infostand uses it).

- [ ] **Step 4: `RoleplayAuthorizationsView`**

If no HQ, a note; else a checkbox per rank; toggle sends `RpSetHqRankComposer`. Staff-only editable:

```tsx
import { RpSetHqRankComposer } from '@nitrots/nitro-renderer';
import { FC } from 'react';
import { IsRpStaff, SendMessageComposer } from '../../../../api';
import { Column, Flex, Text } from '../../../../common';

interface Rank { rankId: number; rankOrder: number; rankName: string; authorized: boolean; }
interface Props { roomCorp: { corpId: number; ranks: Rank[] } | null; className?: string; }

export const RoleplayAuthorizationsView: FC<Props> = ({ roomCorp = null, className = '' }) =>
{
    const staff = IsRpStaff();

    if(!roomCorp || roomCorp.corpId <= 0)
        return (
            <Column gap={ 1 } className={ className }>
                <Text bold>Authorizations</Text>
                <Text className="text-muted">Assign a headquarters first.</Text>
            </Column>
        );

    const toggle = (rankId: number, authorized: boolean) =>
        SendMessageComposer(new RpSetHqRankComposer(rankId, authorized));

    return (
        <Column gap={ 1 } className={ className }>
            <Text bold>Authorizations</Text>
            <Text>Ranks allowed to work at this headquarters.</Text>
            { roomCorp.ranks.map(rank => (
                <Flex key={ rank.rankId } gap={ 1 } alignItems="center">
                    <input type="checkbox" disabled={ !staff } checked={ rank.authorized }
                        onChange={ event => toggle(rank.rankId, event.target.checked) } />
                    <Text>{ rank.rankName }</Text>
                </Flex>
            )) }
            { !staff && <Text small className="text-muted">Only staff can change authorizations.</Text> }
        </Column>
    );
}
```
The authoritative re-render comes from the echoed `RpRoomCorpComposer` updating the parent's `roomCorp` (the checkbox reflects `rank.authorized` from state, so no local optimistic state needed).

- [ ] **Step 5: `RoleplayEmergenciesView`**

Three checkboxes bound to the room flags; always editable; toggle sends `RpSetEmergencyComposer`:

```tsx
import { RpSetEmergencyComposer } from '@nitrots/nitro-renderer';
import { FC } from 'react';
import { SendMessageComposer } from '../../../../api';
import { Column, Flex, Text } from '../../../../common';

interface Props { roomCorp: { allowMedical: boolean; allowPolice: boolean; allowStaff: boolean } | null; className?: string; }

export const RoleplayEmergenciesView: FC<Props> = ({ roomCorp = null, className = '' }) =>
{
    const set = (category: number, enabled: boolean) =>
        SendMessageComposer(new RpSetEmergencyComposer(category, enabled));

    const medical = roomCorp ? roomCorp.allowMedical : true;
    const police = roomCorp ? roomCorp.allowPolice : true;
    const staff = roomCorp ? roomCorp.allowStaff : true;

    return (
        <Column gap={ 1 } className={ className }>
            <Text bold>Emergencies</Text>
            <Text>Which outside services may work in this room, even when it isn't their headquarters.</Text>
            <Flex gap={ 1 } alignItems="center">
                <input type="checkbox" checked={ medical } onChange={ event => set(0, event.target.checked) } />
                <Text>Medical</Text>
            </Flex>
            <Flex gap={ 1 } alignItems="center">
                <input type="checkbox" checked={ police } onChange={ event => set(1, event.target.checked) } />
                <Text>Police</Text>
            </Flex>
            <Flex gap={ 1 } alignItems="center">
                <input type="checkbox" checked={ staff } onChange={ event => set(2, event.target.checked) } />
                <Text>Staff</Text>
            </Flex>
        </Column>
    );
}
```

- [ ] **Step 6: Build**

From `client/`: `yarn build`. Expected: success. Fix any import-path mismatches (`IsRpStaff`, `Flex`/`Column`/`Text` from `../../../../common`, `useMessageEvent` from `../../../../hooks`) by checking a sibling component's imports.

- [ ] **Step 7: Commit (client submodule)**

```bash
cd client
git add src/components/navigator/views/room-settings/
git commit -m "feat(corps): Room settings Roleplay HQ / Authorizations / Emergencies pages

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Ship to beta (both submodule pointers, changelog)

**Files:**
- Modify: `CHANGELOG.md` (new entry)
- Modify: parent gitlinks `emulator`, `client`

**Interfaces:**
- Consumes: pushed submodule commits from Tasks 1–6.

- [ ] **Step 1: Push both submodules**

```bash
cd emulator && git push origin HEAD:pixelrp && cd ..
cd client && git push origin HEAD:pixelrp && cd ..
```

- [ ] **Step 2: Changelog entry**

In `CHANGELOG.md`, directly above the current top release, add:

```markdown
## 2026-08-31 — Headquarters, authorizations and emergencies

### Added

- **Rooms can be a corporation's headquarters.** In Room settings >
  Roleplay > Corporations, staff can point a room at a corporation. Once a
  corporation has a headquarters, its employees can only clock in where
  they're meant to work - at that headquarters, or anywhere an emergency
  service lets them in. Corporations with no headquarters keep working
  anywhere, as before.
- **Pick who works where.** Authorizations lists the corporation's ranks
  with a checkbox each - uncheck a rank and they can't clock in at that
  headquarters. Every rank starts allowed.
- **Emergency services.** Emergencies lets a room admit Medical, Police
  and Staff from outside - so hospital staff and officers can work a scene
  anywhere that allows them. All three are allowed by default; the room
  owner or staff can change them.
- **Leave your post, clock out.** If you walk away from where you're
  allowed to work - or your rank loses access mid-shift - you're clocked
  out on the spot.
```

- [ ] **Step 3: Bump pointers + commit (parent, on `beta`)**

```bash
git add emulator client CHANGELOG.md
git commit -m "feat(corps): room headquarters, authorizations and emergencies (bump emulator + client)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
Verify first: `git diff --cached --submodule=log` shows both `emulator` and `client` advancing to the pushed heads, and only these three paths are staged.

- [ ] **Step 4: Push beta (deploys; auto-applies migration 53)**

```bash
git push origin beta
```

- [ ] **Step 5: Watch the deploy**

```bash
gh run watch $(gh run list --workflow deploy-beta.yml --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status
```
Expected: success. A failure at "Applying database patches" means the migration; at the emulator build/READY step means the C#; capture the failing step's log tail and report.

- [ ] **Step 6: Hand off for in-game verification**

Report to the user what to test on beta (staff account): Room settings > Roleplay > Corporations; assign an HQ (Headquarters dropdown), watch Authorizations populate all-checked; uncheck a rank; toggle Emergencies; then in-game confirm an employee can `:startwork` only at an authorized HQ (or an emergency-allowed room) and gets clocked out on leaving. Per project convention, the in-game check is the user's.

---

## Self-Review

- **Spec coverage:** schema/service_type/tables → Task 1; RpRoomCorpComposer + settings-open send → Task 2; three write handlers with the exact gating (staff for HQ/rank, owner-or-staff for emergency) → Task 3; the four-way work-gate + continuous tick + copy strings → Task 4; renderer packets → Task 5; parent state + three pages + staff gating → Task 6; rollout/back-compat/changelog → Task 7. Non-goals (no service_type UI, corp-wide emergency) respected — no task adds them.
- **Placeholder scan:** logic-bearing code (SQL, EvaluateWork, three handlers, tick, all three React pages) is given in full. Mirror-boilerplate (renderer Event/Composer/parser TS, header-const lines) points at the exact precedent file to copy shape from with the precise field layout — deliberate, because the repo's import paths are the ground truth and transcribing them blind risks drift; Task 5's steps name the precedent file for each.
- **Type/name consistency:** wire ids 3957–3960 and internal 4395x/4396x are consistent across Tasks 2, 3, 5. `CorporationUtility.BuildRoomCorp` (Task 2) is consumed by Tasks 2/3; `EvaluateWork` (Task 4) signature `(bool Ok, string Reason)` used in StartShift + tick. Composer field order matches the parser field order in the wire contract. `RoomCorpState`/`ranks` shape is consistent between parent (Task 6 Step 1) and the three page components (Steps 3–5).
- **Known soft spots flagged for implementers:** exact packet-writer/reader method names, `IPacketEvent`/`IIncomingPacket` shape, and renderer import paths are all pinned to a named precedent file to copy, since no local compiler catches TS drift until `yarn build` (Task 5/6 Step 6) and the emulator only at `docker compose build`.
