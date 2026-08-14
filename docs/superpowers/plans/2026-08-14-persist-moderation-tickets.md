# Persist Moderation Tickets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Moderation tickets are written to `moderation_tickets` and reloaded on
startup, so open and picked reports survive an emulator restart or deploy.

**Architecture:** `ModerationTicket` stops holding live `Habbo`/`RoomData`
references and carries the ids, usernames and room name that the packets
actually write — the only shape a database row can be rebuilt into, because
`PlusEnvironment.GetHabboById` resolves online users only. `ModerationManager`
gains the INSERT (taking the row's `AUTO_INCREMENT` id), the startup load of
`status IN ('open','picked')`, and write-through methods the four packet
handlers call instead of mutating ticket fields directly.

**Tech Stack:** C# / .NET 7 (`Plus Emulator.csproj`, `Nullable` and
`ImplicitUsings` enabled, LangVersion 11), MySQL 8 via the legacy
`IDatabase.GetQueryReactor()` adapter, `System.Text.Json`, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-14-persist-moderation-tickets-design.md`

## Global Constraints

- Work happens in the **`emulator` submodule** on branch `pixelrp`. In this
  worktree the submodule starts **detached** — `git -C emulator checkout pixelrp`
  before the first commit.
- The parent repo commits only the submodule pointer bump and `CHANGELOG.md`.
- SQL updates are numbered files in `emulator/Resources/SQLs/Updates/`. Never
  edit `Resources/SQLs/Original Database.sql`. The deploy workflow replays any
  file not yet in the prod `_applied_sql_updates` table, so a committed update
  file reaches production on its own.
- Deploy is `gh workflow run deploy.yml` — never a manual SSH deploy, which
  skips the update screen, the countdown toast and the graceful shutdown.
- `CHANGELOG.md` is player-facing: describe what someone sees or does, no file
  paths, commit hashes or component names.
- The query adapter **swallows exceptions** — it logs through
  `ExceptionLogger.LogQueryError` and returns a default (`0` from
  `InsertQuery()`). Detect failure by checking the returned value, never by
  wrapping calls in `try`/`catch`.
- The `ModerationTicketStatus` enum names must keep lower-casing to exactly the
  database enum values (`open`, `picked`, `resolved`, `abusive`, `invalid`,
  `deleted`) — `ToString().ToLowerInvariant()` is the whole mapping.

## Local environment setup (do this once, before Task 1)

The running Compose project is `pixelrp`, configured from the **main checkout**
(`/Users/rybealey/Documents/Personal/pixelrp/plus`). To build the emulator from
this worktree's source against that same database, run Compose from the worktree
with the project name pinned:

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402
cp -n /Users/rybealey/Documents/Personal/pixelrp/plus/.env .env
mkdir -p nitro/assets/c_images/camera
```

`.env` is gitignored, so the copy cannot be committed. The `mkdir` exists only so
the emulator's camera bind mount resolves in this directory.

**Always name the `emulator` service explicitly.** A bare
`docker compose -p pixelrp up -d` from this worktree would recreate `web` against
this directory's empty `nitro/`, which breaks the locally served client.

Two shell helpers used throughout:

```bash
# Build + restart just the emulator from worktree source
docker compose -p pixelrp build emulator && docker compose -p pixelrp up -d emulator
```

```bash
# Run SQL against the local database
PW=$(grep ^DB_PASSWORD /Users/rybealey/Documents/Personal/pixelrp/plus/.env | cut -d= -f2)
docker compose -p pixelrp exec -T db mysql -upixelrp -p"$PW" pixelrp -e "SELECT 1;"
```

Local accounts (`rank` is a reserved word — always backtick it):
`ClaudeTest` (id 5, rank 4, a regular player — the reporter), `Admin` (id 1,
rank 9 — the moderator), `pixelrp_tester` (id 3, rank 1 — spare report target).

Log in by minting an SSO ticket and opening the client with it:

```bash
docker compose -p pixelrp exec cms php artisan tinker --execute='echo App\Models\User::where("username","ClaudeTest")->first()->ssoTicket();'
```

then `http://localhost:8080/nitro-assets/client/index.html?sso=<ticket>`. A
ticket is single-use — mint a fresh one for every login, including every
re-login after a restart.

---

### Task 1: Schema — the two columns the shipped table lacks

**Files:**
- Create: `emulator/Resources/SQLs/Updates/22_PersistModerationTickets.sql`

**Interfaces:**
- Consumes: nothing.
- Produces: `moderation_tickets.category` (int) and
  `moderation_tickets.reported_chats` (text, nullable), which Tasks 3 and 4
  read and write.

The table already ships with `id`, `score`, `type`, `status`, `sender_id`,
`reported_id`, `moderator_id`, `message`, `room_id`, `room_name` and
`timestamp`. Only two columns are missing: the client reads the composer's
`Type` field as its displayed `categoryId` and the `Category` field as
`reportedCategoryId`, so both must round-trip; and the reporter's quoted chat
lines have nowhere to live at all.

- [ ] **Step 1: Write the update file**

Create `emulator/Resources/SQLs/Updates/22_PersistModerationTickets.sql`:

```sql
-- Moderation tickets are now persisted, so they survive an emulator restart.
-- Two fields on a ticket have nowhere to live in the shipped table:
--   category       the CFH topic the reporter picked. The existing `type`
--                  column holds the other category field, which is the one
--                  the client displays in the Open Issues list.
--   reported_chats the chat lines the reporter quoted as evidence, stored as
--                  a JSON array. Nullable: a NULL or unreadable value loads
--                  as no chats rather than failing startup.

ALTER TABLE `moderation_tickets`
    ADD COLUMN `category` int(11) NOT NULL DEFAULT 0 AFTER `type`,
    ADD COLUMN `reported_chats` text NULL DEFAULT NULL AFTER `message`;
```

- [ ] **Step 2: Apply it locally**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402
PW=$(grep ^DB_PASSWORD /Users/rybealey/Documents/Personal/pixelrp/plus/.env | cut -d= -f2)
docker compose -p pixelrp exec -T db mysql -upixelrp -p"$PW" pixelrp < emulator/Resources/SQLs/Updates/22_PersistModerationTickets.sql
```

Expected: no output. A second run fails with "Duplicate column name" — that is
the correct signal it already applied, not an error to fix.

- [ ] **Step 3: Verify the columns exist**

```bash
PW=$(grep ^DB_PASSWORD /Users/rybealey/Documents/Personal/pixelrp/plus/.env | cut -d= -f2)
docker compose -p pixelrp exec -T db mysql -upixelrp -p"$PW" pixelrp -e "SHOW COLUMNS FROM moderation_tickets;"
```

Expected: 13 rows, including `category` (`int`, `NO`, default `0`) and
`reported_chats` (`text`, `YES`, default `NULL`).

- [ ] **Step 4: Commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402/emulator
git checkout pixelrp
git add Resources/SQLs/Updates/22_PersistModerationTickets.sql
git commit -m "feat(moderation): SQL update 22 - columns for persisting tickets

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Reshape `ModerationTicket` onto ids and usernames

**Files:**
- Modify: `emulator/HabboHotel/Moderation/ModerationTicket.cs` (whole file)
- Modify: `emulator/HabboHotel/Moderation/ModerationManager.cs:244-246`
- Modify: `emulator/Communication/Packets/Outgoing/Moderation/ModeratorSupportTicketComposer.cs:28-36`
- Modify: `emulator/Communication/Packets/Outgoing/Moderation/ModeratorInitComposer.cs:15-41`
- Modify: `emulator/Communication/Packets/Outgoing/Moderation/ModeratorTicketChatlogComposer.cs:25-41`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/GetModeratorTicketChatlogsEvent.cs:22-24`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/CloseTicketEvent.cs:31-39`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/PickTicketEvent.cs:26`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ReleaseTicketEvent.cs:27`
- Modify: `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs:126-129`
- Modify: `emulator/Communication/RCON/Commands/User/ReloadUserRankCommand.cs:41-44`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ModerationTicket` with `int SenderId`, `string SenderUsername`,
  `int ReportedId`, `string ReportedUsername`, `int ModeratorId` (`0` = unpicked),
  `string ModeratorUsername`, `uint RoomId` (`0` = none), `string RoomName`,
  and a 15-argument constructor taking those flat values. Tasks 3 and 4 build
  tickets through that constructor and assign those properties.

This task is one atomic refactor — the build is red between the first edit and
the last. It changes no behaviour except the `ModeratorInitComposer` fix in
Step 5.

- [ ] **Step 1: Rewrite `ModerationTicket.cs`**

Replace the whole file with:

```csharp
using Plus.HabboHotel.Rooms;
using Plus.HabboHotel.Users;

namespace Plus.HabboHotel.Moderation;

public class ModerationTicket
{
    public List<string> ReportedChats;

    /// <summary>A freshly submitted report, taken from the live session objects.</summary>
    public ModerationTicket(int id, int type, int category, double timestamp, int priority, Habbo? sender, Habbo? reported, string issue, RoomData? room,
        List<string> reportedChats)
        : this(id, type, category, timestamp, priority,
            sender?.Id ?? 0, sender?.Username ?? string.Empty,
            reported?.Id ?? 0, reported?.Username ?? string.Empty,
            0, string.Empty, issue, room?.Id ?? 0, room?.Name ?? string.Empty, reportedChats)
    {
    }

    /// <summary>
    /// A ticket rebuilt from its `moderation_tickets` row. Ids and usernames are
    /// carried as plain values because after a restart the reporter, the reported
    /// user and the picking moderator are usually all offline, and
    /// PlusEnvironment.GetHabboById only ever resolves users who are online.
    /// </summary>
    public ModerationTicket(int id, int type, int category, double timestamp, int priority, int senderId, string senderUsername, int reportedId,
        string reportedUsername, int moderatorId, string moderatorUsername, string issue, uint roomId, string roomName, List<string>? reportedChats)
    {
        Id = id;
        Type = type;
        Category = category;
        Timestamp = timestamp;
        Priority = priority;
        SenderId = senderId;
        SenderUsername = senderUsername;
        ReportedId = reportedId;
        ReportedUsername = reportedUsername;
        ModeratorId = moderatorId;
        ModeratorUsername = moderatorUsername;
        Issue = issue;
        RoomId = roomId;
        RoomName = roomName;
        Answered = false;
        ReportedChats = reportedChats ?? new();
    }

    public int Id { get; set; }
    public int Type { get; set; }
    public int Category { get; set; }
    public double Timestamp { get; set; }
    public int Priority { get; set; }
    public bool Answered { get; set; }
    public int SenderId { get; set; }
    public string SenderUsername { get; set; }
    public int ReportedId { get; set; }
    public string ReportedUsername { get; set; }

    /// <summary>The moderator who picked this ticket, or 0 while it is unpicked.</summary>
    public int ModeratorId { get; set; }

    public string ModeratorUsername { get; set; }
    public string Issue { get; set; }

    /// <summary>The room the report was made in, or 0 if the reporter was not in one.</summary>
    public uint RoomId { get; set; }

    public string RoomName { get; set; }

    /// <summary>The ticket's tab, as seen by the moderator whose id is passed in.</summary>
    public int GetStatus(int id)
    {
        if (ModeratorId == 0)
            return 1;
        if (ModeratorId == id && !Answered)
            return 2;
        return 3;
    }
}
```

- [ ] **Step 2: Update the two lookups in `ModerationManager.cs`**

At lines 244-246, `Sender.Id` becomes `SenderId`:

```csharp
    public bool UserHasTickets(int userId) => _modTickets.Any(x => x.Value.SenderId == userId && x.Value.Answered == false);

    public ModerationTicket GetTicketBySenderId(int userId) => _modTickets.FirstOrDefault(x => x.Value.SenderId == userId).Value;
```

- [ ] **Step 3: Update `ModeratorSupportTicketComposer.cs`**

Replace lines 28-36 (from `// Sender ID` through `// Room Id`) with:

```csharp
        packet.WriteInteger(_ticket.SenderId); // Sender ID
        //base.WriteInteger(1);
        packet.WriteString(_ticket.SenderUsername); // Sender Name
        packet.WriteInteger(_ticket.ReportedId); // Reported ID
        packet.WriteString(_ticket.ReportedUsername); // Reported Name
        packet.WriteInteger(_ticket.ModeratorId); // Moderator ID
        packet.WriteString(_ticket.ModeratorUsername); // Mod Name
        packet.WriteString(_ticket.Issue); // Issue
        packet.WriteUInteger(_ticket.RoomId); // Room Id
```

- [ ] **Step 4: Update `ModeratorTicketChatlogComposer.cs`**

Lines 25-26 become:

```csharp
        packet.WriteInteger(_ticket.SenderId);
        packet.WriteInteger(_ticket.ReportedId);
```

and line 41 becomes:

```csharp
            packet.WriteString(string.IsNullOrEmpty(_ticket.ReportedUsername) ? "No username" : _ticket.ReportedUsername);
```

- [ ] **Step 5: Update `ModeratorInitComposer.cs` — and fix the tab it reports**

This composer sends the whole ticket list to a moderator at login, which is how
a restored ticket reaches the mod tools at all. Line 28 calls
`ticket.GetStatus(ticket.Id)` — it passes the *ticket's* id where a *moderator's*
id belongs, so a picked ticket compares `ModeratorId == ticketId`, fails, and is
reported as closed. Until now that only mattered for a moderator logging in
mid-session; once tickets survive restarts, every restored picked ticket would
land in the wrong tab. The composer needs the viewing user's id.

Change the field block and constructor (lines 9-20) to:

```csharp
    private readonly ICollection<string> _userPresets;
    private readonly ICollection<string> _roomPresets;
    private readonly ICollection<ModerationTicket> _tickets;

    // Which tab a ticket belongs in is relative to who is looking: a ticket
    // picked by *this* moderator is "mine", anyone else's is not.
    private readonly int _viewerId;

    public uint MessageId => ServerPacketHeader.ModeratorInitComposer;

    public ModeratorInitComposer(int viewerId, ICollection<string> userPresets, ICollection<string> roomPresets, ICollection<ModerationTicket> tickets)
    {
        _viewerId = viewerId;
        _userPresets = userPresets;
        _roomPresets = roomPresets;
        _tickets = tickets;
    }
```

Then line 28 and lines 33-41:

```csharp
            packet.WriteInteger(ticket.GetStatus(_viewerId)); // Tab ID
```

```csharp
            packet.WriteInteger(ticket.SenderId); // Sender ID
            packet.WriteInteger(1);
            packet.WriteString(ticket.SenderUsername); // Sender Name
            packet.WriteInteger(ticket.ReportedId); // Reported ID
            packet.WriteString(ticket.ReportedUsername); // Reported Name
            packet.WriteInteger(ticket.ModeratorId); // Moderator ID
            packet.WriteString(ticket.ModeratorUsername); // Mod Name
            packet.WriteString(ticket.Issue); // Issue
            packet.WriteUInteger(ticket.RoomId); // Room Id
```

- [ ] **Step 6: Pass the viewer id at both call sites**

`SSOTicketEvent.cs` line 126:

```csharp
                session.Send(new ModeratorInitComposer(
                    session.GetHabbo().Id,
                    _moderationManager.UserMessagePresets,
                    _moderationManager.RoomMessagePresets,
                    _moderationManager.GetTickets));
```

`ReloadUserRankCommand.cs` line 41:

```csharp
            client.Send(new ModeratorInitComposer(
                client.GetHabbo().Id,
                _moderationManager.UserMessagePresets,
                _moderationManager.RoomMessagePresets,
                _moderationManager.GetTickets));
```

- [ ] **Step 7: Update `GetModeratorTicketChatlogsEvent.cs`**

Lines 22-24 become:

```csharp
        if (!_moderationManager.TryGetTicket(ticketId, out var ticket) || ticket.RoomId == 0)
            return Task.CompletedTask;
        if (!RoomFactory.TryGetData(ticket.RoomId, out var data))
            return Task.CompletedTask;
```

- [ ] **Step 8: Update the three handlers that touch the fields directly**

`CloseTicketEvent.cs` lines 31-39 — note this also removes a latent
`NullReferenceException` on a ticket that was never picked:

```csharp
        if (ticket.ModeratorId != session.GetHabbo().Id)
            return Task.CompletedTask;
        var client = _clientManager.GetClientByUserId(ticket.SenderId);
        if (client != null) client.Send(new ModeratorSupportTicketResponseComposer(result));
        if (result == 2)
        {
            using var connection = _database.Connection();
            connection.Execute("UPDATE `user_info` SET `cfhs_abusive` = `cfhs_abusive` + 1 WHERE `user_id` = @senderId LIMIT 1",
                new { senderId = ticket.SenderId });
        }
```

`PickTicketEvent.cs` line 26:

```csharp
        ticket.ModeratorId = session.GetHabbo().Id;
        ticket.ModeratorUsername = session.GetHabbo().Username;
```

`ReleaseTicketEvent.cs` line 27:

```csharp
            ticket.ModeratorId = 0;
            ticket.ModeratorUsername = string.Empty;
```

- [ ] **Step 9: Build**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402
docker compose -p pixelrp build emulator 2>&1 | tail -5
```

Expected: build succeeds. If the compiler reports any remaining `.Sender`,
`.Reported`, `.Moderator` or `.Room` member on a `ModerationTicket`, fix that
call site the same way and note it in the task report — the file list above was
taken from a full grep, so a miss means something changed underneath.

- [ ] **Step 10: Boot and confirm reporting still works end to end**

```bash
docker compose -p pixelrp up -d emulator && sleep 15
docker compose -p pixelrp logs --since 60s emulator 2>&1 | grep -E "READY|ERROR|Exception" | tail -5
```

Expected: `EMULATOR -> READY!`, no exceptions.

Then, in two browser tabs (fresh SSO ticket each): log in `Admin` and
`ClaudeTest`, put both in the same room, and from `ClaudeTest` use Help →
"Someone is misbehaving" → pick `Admin` → select a chat line and a topic →
send. In the `Admin` tab open the mod tools Tickets panel.

Expected: the ticket is listed in Open Issues with `ClaudeTest` as reporter and
`Admin` as the reported user, and the Chatlog button shows the quoted line.
This is the pre-existing behaviour — the task is a refactor, so anything
different here is a regression to fix before committing.

- [ ] **Step 11: Commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402/emulator
git add HabboHotel/Moderation/ModerationTicket.cs HabboHotel/Moderation/ModerationManager.cs \
  Communication/Packets/Outgoing/Moderation/ModeratorSupportTicketComposer.cs \
  Communication/Packets/Outgoing/Moderation/ModeratorInitComposer.cs \
  Communication/Packets/Outgoing/Moderation/ModeratorTicketChatlogComposer.cs \
  Communication/Packets/Incoming/Moderation/GetModeratorTicketChatlogsEvent.cs \
  Communication/Packets/Incoming/Moderation/CloseTicketEvent.cs \
  Communication/Packets/Incoming/Moderation/PickTicketEvent.cs \
  Communication/Packets/Incoming/Moderation/ReleaseTicketEvent.cs \
  Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs \
  Communication/RCON/Commands/User/ReloadUserRankCommand.cs
git commit -m "refactor(moderation): tickets carry ids and usernames, not Habbo refs

A ticket rebuilt from a database row cannot hold live Habbo/RoomData
references: GetHabboById resolves online users only, so a restored ticket
would render with id 0 and a blank username. The composers only ever read
.Id and .Username off those references anyway.

Also passes the viewing moderator's id to ModeratorInitComposer, which was
passing the ticket's own id into GetStatus and so reporting every picked
ticket as closed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Write the ticket on submit, load open tickets on startup

**Files:**
- Create: `emulator/HabboHotel/Moderation/ModerationTicketStatus.cs`
- Modify: `emulator/HabboHotel/Moderation/ModerationManager.cs` (usings, fields, `Init()`, `TryAddTicket`)
- Modify: `emulator/Communication/Packets/Incoming/Moderation/SubmitNewTicketEvent.cs:66-76`

**Interfaces:**
- Consumes: `ModerationTicket`'s 15-argument constructor and its
  `SenderId`/`ReportedId`/`ModeratorId`/`RoomId`/`RoomName` properties (Task 2);
  the `category` and `reported_chats` columns (Task 1).
- Produces: `enum ModerationTicketStatus { Open, Picked, Resolved, Abusive,
  Invalid, Deleted }`, and `ModerationManager.UpdateTicketStatus(ModerationTicket,
  ModerationTicketStatus)` (private) which Task 4's write-through methods call.

- [ ] **Step 1: Add the status enum**

Create `emulator/HabboHotel/Moderation/ModerationTicketStatus.cs`:

```csharp
namespace Plus.HabboHotel.Moderation;

/// <summary>
/// Mirrors the `status` enum on `moderation_tickets`. The member names must keep
/// lower-casing to exactly the database's values — that is the entire mapping.
/// </summary>
public enum ModerationTicketStatus
{
    Open,
    Picked,
    Resolved,
    Abusive,
    Invalid,
    Deleted
}
```

- [ ] **Step 2: Add the usings and the fallback-id field to `ModerationManager.cs`**

At the top of the file, add to the existing usings:

```csharp
using System.Text.Json;
using Plus.HabboHotel.Users;
```

Then replace the `private int _ticketCount = 1;` field (line 23) with:

```csharp
    /// <summary>
    /// Ids for tickets that could not be written (see <see cref="InsertTicket" />).
    /// Counts down from 0 so these can never collide with a real row id.
    /// </summary>
    private int _unpersistedTicketId;
```

- [ ] **Step 3: Replace `TryAddTicket` and add the insert**

`TryAddTicket` currently reads `ticket.Id = _ticketCount++;`. Replace it (lines
236-240) with:

```csharp
    public bool TryAddTicket(ModerationTicket ticket)
    {
        ticket.Id = InsertTicket(ticket);
        return _modTickets.TryAdd(ticket.Id, ticket);
    }

    /// <summary>
    /// Writes a new report and returns its row id. A database failure must not
    /// cost the hotel the report — the query adapter logs and returns 0, so fall
    /// back to a negative id that keeps the ticket usable in memory for this
    /// session and is plainly not a row.
    /// </summary>
    private int InsertTicket(ModerationTicket ticket)
    {
        using var dbClient = _database.GetQueryReactor();
        dbClient.SetQuery(
            "INSERT INTO `moderation_tickets` (`score`,`type`,`category`,`status`,`sender_id`,`reported_id`,`moderator_id`,`message`,`reported_chats`,`room_id`,`room_name`,`timestamp`) " +
            "VALUES (@score, @type, @category, 'open', @senderId, @reportedId, 0, @message, @reportedChats, @roomId, @roomName, @timestamp);");
        dbClient.AddParameter("score", ticket.Priority);
        dbClient.AddParameter("type", ticket.Type);
        dbClient.AddParameter("category", ticket.Category);
        dbClient.AddParameter("senderId", ticket.SenderId);
        dbClient.AddParameter("reportedId", ticket.ReportedId);
        dbClient.AddParameter("message", ticket.Issue);
        dbClient.AddParameter("reportedChats", JsonSerializer.Serialize(ticket.ReportedChats));
        dbClient.AddParameter("roomId", ticket.RoomId);
        dbClient.AddParameter("roomName", ticket.RoomName);
        dbClient.AddParameter("timestamp", ticket.Timestamp);
        var id = Convert.ToInt32(dbClient.InsertQuery());
        if (id > 0)
            return id;
        _logger.LogError("Could not save the moderation ticket from user {SenderId}. It will reach staff this session but is lost on the next restart.",
            ticket.SenderId);
        return Interlocked.Decrement(ref _unpersistedTicketId);
    }

    /// <summary>Writes a ticket's status and picking moderator through to its row.</summary>
    private void UpdateTicketStatus(ModerationTicket ticket, ModerationTicketStatus status)
    {
        if (ticket.Id <= 0) // Never persisted (see InsertTicket) — no row to update.
            return;
        using var dbClient = _database.GetQueryReactor();
        dbClient.SetQuery("UPDATE `moderation_tickets` SET `status` = @status, `moderator_id` = @moderatorId WHERE `id` = @id LIMIT 1;");
        dbClient.AddParameter("status", status.ToString().ToLowerInvariant());
        dbClient.AddParameter("moderatorId", ticket.ModeratorId);
        dbClient.AddParameter("id", ticket.Id);
        dbClient.RunQuery();
    }

    /// <summary>
    /// The quoted chat lines are stored as a JSON array. Anything unreadable loads
    /// as no chats rather than taking startup down with it.
    /// </summary>
    private List<string> ParseReportedChats(object value)
    {
        if (value == DBNull.Value)
            return new();
        var raw = Convert.ToString(value);
        if (string.IsNullOrEmpty(raw))
            return new();
        try
        {
            return JsonSerializer.Deserialize<List<string>>(raw) ?? new();
        }
        catch (JsonException)
        {
            _logger.LogWarning("Could not read the quoted chats on a moderation ticket; loading it without them.");
            return new();
        }
    }
```

- [ ] **Step 4: Load open and picked tickets in `Init()`**

Add `_modTickets` to the defensive clears at the top of `Init()` (after the
`_bans.Clear()` line, ~line 62):

```csharp
        if (!_modTickets.IsEmpty)
            _modTickets.Clear();
```

Then, immediately before the closing `_logger.LogInformation(...)` block at the
end of `Init()` (~line 175), add:

```csharp
        using (var dbClient = _database.GetQueryReactor())
        {
            // LEFT JOINs rather than INNER: a row whose users have since been
            // deleted must be counted and reported, not silently dropped by the
            // query.
            dbClient.SetQuery(
                "SELECT `t`.`id`, `t`.`score`, `t`.`type`, `t`.`category`, `t`.`message`, `t`.`reported_chats`, `t`.`room_id`, `t`.`room_name`, `t`.`timestamp`, " +
                "`t`.`sender_id`, `s`.`username` AS `sender_username`, `t`.`reported_id`, `r`.`username` AS `reported_username`, " +
                "`t`.`moderator_id`, `m`.`username` AS `moderator_username` " +
                "FROM `moderation_tickets` AS `t` " +
                "LEFT JOIN `users` AS `s` ON `s`.`id` = `t`.`sender_id` " +
                "LEFT JOIN `users` AS `r` ON `r`.`id` = `t`.`reported_id` " +
                "LEFT JOIN `users` AS `m` ON `m`.`id` = `t`.`moderator_id` " +
                "WHERE `t`.`status` IN ('open', 'picked') ORDER BY `t`.`id`;");
            var openTickets = dbClient.GetTable();
            var skipped = 0;
            if (openTickets != null)
            {
                foreach (DataRow row in openTickets.Rows)
                {
                    var senderUsername = row["sender_username"] == DBNull.Value ? string.Empty : Convert.ToString(row["sender_username"]);
                    var reportedUsername = row["reported_username"] == DBNull.Value ? string.Empty : Convert.ToString(row["reported_username"]);

                    // A ticket that can no longer name who reported whom is no use
                    // to staff.
                    if (string.IsNullOrEmpty(senderUsername) || string.IsNullOrEmpty(reportedUsername))
                    {
                        skipped++;
                        continue;
                    }
                    var moderatorUsername = row["moderator_username"] == DBNull.Value ? string.Empty : Convert.ToString(row["moderator_username"]);

                    // The moderator who picked it has since been deleted; hand the
                    // ticket back to the open queue rather than to a blank name.
                    var moderatorId = string.IsNullOrEmpty(moderatorUsername) ? 0 : Convert.ToInt32(row["moderator_id"]);
                    var ticket = new ModerationTicket(Convert.ToInt32(row["id"]), Convert.ToInt32(row["type"]), Convert.ToInt32(row["category"]),
                        Convert.ToDouble(row["timestamp"]), Convert.ToInt32(row["score"]),
                        Convert.ToInt32(row["sender_id"]), senderUsername,
                        Convert.ToInt32(row["reported_id"]), reportedUsername,
                        moderatorId, moderatorUsername,
                        Convert.ToString(row["message"]), Convert.ToUInt32(row["room_id"]), Convert.ToString(row["room_name"]),
                        ParseReportedChats(row["reported_chats"]));
                    _modTickets.TryAdd(ticket.Id, ticket);
                }
            }
            if (skipped > 0)
                _logger.LogWarning("Skipped " + skipped + " moderation tickets whose reporter or reported user no longer exists.");
        }
```

and add one more line to the existing log block at the end of `Init()`:

```csharp
        _logger.LogInformation("Loaded " + _modTickets.Count + " open moderation tickets.");
```

- [ ] **Step 5: Drop the dead INSERT from `SubmitNewTicketEvent.cs`**

Line 66's placeholder id is now overwritten by `TryAddTicket`, so make that
obvious, and delete the commented-out query. Replace lines 66-76 with:

```csharp
        // Id 0 is a placeholder — TryAddTicket replaces it with the row id.
        var ticket = new ModerationTicket(0, type, category, UnixTimestamp.GetNow(), 1, session.GetHabbo(), reportedUser, message, session.GetHabbo().CurrentRoom, chats);
        if (!_moderationManager.TryAddTicket(ticket))
            return Task.CompletedTask;
        using (var dbClient = _database.GetQueryReactor())
        {
            dbClient.RunQuery($"UPDATE `user_info` SET `cfhs` = `cfhs` + '1' WHERE `user_id` = '{session.GetHabbo().Id}' LIMIT 1");
        }
```

- [ ] **Step 6: Build and boot**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402
docker compose -p pixelrp build emulator 2>&1 | tail -5
docker compose -p pixelrp up -d emulator && sleep 15
docker compose -p pixelrp logs --since 60s emulator 2>&1 | grep -E "READY|moderation tickets|ERROR|Exception" | tail -5
```

Expected: build succeeds, `EMULATOR -> READY!`, and a
`Loaded 0 open moderation tickets.` line (the table still holds only whatever
Task 2's test created — which was never written, so 0 is correct here).

- [ ] **Step 7: Submit a report and confirm the row**

Log in `Admin` and `ClaudeTest` in two tabs (fresh SSO ticket each), both in the
same room, and send a report from `ClaudeTest` against `Admin` with at least one
chat line quoted and a topic chosen. Then:

```bash
PW=$(grep ^DB_PASSWORD /Users/rybealey/Documents/Personal/pixelrp/plus/.env | cut -d= -f2)
docker compose -p pixelrp exec -T db mysql -upixelrp -p"$PW" pixelrp -e "SELECT id, score, type, category, status, sender_id, reported_id, moderator_id, message, reported_chats, room_id, room_name FROM moderation_tickets\G"
```

Expected: exactly one row — `status` `open`, `sender_id` 5, `reported_id` 1,
`moderator_id` 0, the reporter's message in `message`, a JSON array such as
`["hello there"]` in `reported_chats`, and a non-zero `room_id` with its name.
Confirm the ticket also still appears in `Admin`'s Tickets panel.

- [ ] **Step 8: Restart and confirm the ticket comes back**

```bash
docker compose -p pixelrp restart emulator && sleep 15
docker compose -p pixelrp logs --since 60s emulator 2>&1 | grep -E "READY|moderation tickets" | tail -3
```

Expected: `Loaded 1 open moderation tickets.`

Log `Admin` back in with a fresh SSO ticket and open the mod tools Tickets
panel.

Expected: the ticket is listed in Open Issues, showing `ClaudeTest` as reporter
and `Admin` as reported, with the same category label as before the restart, and
the Chatlog button still shows the quoted line. **This is the behaviour the whole
change exists for** — record it explicitly in the task report.

- [ ] **Step 9: Confirm the reporter is still blocked from double-reporting**

In the `ClaudeTest` tab (re-login with a fresh SSO ticket), try to send a second
report.

Expected: the client says the existing call is still waiting for staff — the
restored ticket is recognised as theirs, not treated as absent.

- [ ] **Step 10: Commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402/emulator
git add HabboHotel/Moderation/ModerationTicketStatus.cs HabboHotel/Moderation/ModerationManager.cs \
  Communication/Packets/Incoming/Moderation/SubmitNewTicketEvent.cs
git commit -m "feat(moderation): persist new tickets and reload open ones at startup

Ticket ids now come from the moderation_tickets AUTO_INCREMENT rather than an
in-process counter, so they cannot collide across a restart. A failed insert
logs and falls back to a negative id so the report still reaches staff.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Write status changes through

**Files:**
- Modify: `emulator/HabboHotel/Moderation/ModerationManager.cs` (three new public methods)
- Modify: `emulator/HabboHotel/Moderation/IModerationManager.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/PickTicketEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ReleaseTicketEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/CloseTicketEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/CallForHelpPendingCallsDeletedEvent.cs`

**Interfaces:**
- Consumes: `UpdateTicketStatus` and `ModerationTicketStatus` (Task 3); the
  ticket's `ModeratorId`/`ModeratorUsername`/`Answered` properties (Task 2).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Add the three write-through methods to `ModerationManager.cs`**

Place them directly after `TryAddTicket`:

```csharp
    public void PickTicket(ModerationTicket ticket, Habbo moderator)
    {
        ticket.ModeratorId = moderator.Id;
        ticket.ModeratorUsername = moderator.Username;
        UpdateTicketStatus(ticket, ModerationTicketStatus.Picked);
    }

    public void ReleaseTicket(ModerationTicket ticket)
    {
        ticket.ModeratorId = 0;
        ticket.ModeratorUsername = string.Empty;
        UpdateTicketStatus(ticket, ModerationTicketStatus.Open);
    }

    public void CloseTicket(ModerationTicket ticket, ModerationTicketStatus status)
    {
        ticket.Answered = true;
        UpdateTicketStatus(ticket, status);
    }
```

- [ ] **Step 2: Declare them on `IModerationManager.cs`**

Add `using Plus.HabboHotel.Users;` at the top, and after the `TryAddTicket`
declaration:

```csharp
    void PickTicket(ModerationTicket ticket, Habbo moderator);
    void ReleaseTicket(ModerationTicket ticket);
    void CloseTicket(ModerationTicket ticket, ModerationTicketStatus status);
```

- [ ] **Step 3: Route `PickTicketEvent.cs` through the manager**

Replace the two assignment lines added in Task 2 (line 26 onward) with:

```csharp
        _moderationManager.PickTicket(ticket, session.GetHabbo());
```

- [ ] **Step 4: Route `ReleaseTicketEvent.cs` through the manager**

Replace the two assignment lines added in Task 2 (line 27 onward) with:

```csharp
            _moderationManager.ReleaseTicket(ticket);
```

- [ ] **Step 5: Route `CloseTicketEvent.cs` through the manager**

Replace `ticket.Answered = true;` (line 41) with:

```csharp
        // The client's result codes: 1 = useless, 2 = abusive, 3 = resolved.
        _moderationManager.CloseTicket(ticket, result switch
        {
            1 => ModerationTicketStatus.Invalid,
            2 => ModerationTicketStatus.Abusive,
            _ => ModerationTicketStatus.Resolved
        });
```

- [ ] **Step 6: Route `CallForHelpPendingCallsDeletedEvent.cs` through the manager**

Replace `pendingTicket.Answered = true;` (line 25) with:

```csharp
                _moderationManager.CloseTicket(pendingTicket, ModerationTicketStatus.Deleted);
```

Add `using Plus.HabboHotel.Moderation;` if the file does not already have it (it
does).

- [ ] **Step 7: Build and boot**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402
docker compose -p pixelrp build emulator 2>&1 | tail -5
docker compose -p pixelrp up -d emulator && sleep 15
docker compose -p pixelrp logs --since 60s emulator 2>&1 | grep -E "READY|moderation tickets|ERROR|Exception" | tail -5
```

Expected: build succeeds, READY, `Loaded 1 open moderation tickets.` (Task 3's
ticket is still open).

- [ ] **Step 8: Pick the ticket and confirm the write**

Log `Admin` in with a fresh SSO ticket, open the mod tools Tickets panel, and
click Pick Issue on the ticket.

```bash
PW=$(grep ^DB_PASSWORD /Users/rybealey/Documents/Personal/pixelrp/plus/.env | cut -d= -f2)
docker compose -p pixelrp exec -T db mysql -upixelrp -p"$PW" pixelrp -e "SELECT id, status, moderator_id FROM moderation_tickets;"
```

Expected: `status` `picked`, `moderator_id` 1.

- [ ] **Step 9: Restart and confirm it returns picked, to the right moderator**

```bash
docker compose -p pixelrp restart emulator && sleep 15
docker compose -p pixelrp logs --since 60s emulator 2>&1 | grep -E "READY|moderation tickets" | tail -3
```

Log `Admin` back in with a fresh SSO ticket and open the Tickets panel.

Expected: `Loaded 1 open moderation tickets.`, and the ticket appears under
`Admin`'s own picked issues — not in Open Issues and not in the closed tab.
(This is what Task 2 Step 5's viewer-id fix buys; if it shows as closed, that
fix regressed.)

- [ ] **Step 10: Release, then close, and confirm both writes**

Release the ticket in the mod tools, then check:

```bash
PW=$(grep ^DB_PASSWORD /Users/rybealey/Documents/Personal/pixelrp/plus/.env | cut -d= -f2)
docker compose -p pixelrp exec -T db mysql -upixelrp -p"$PW" pixelrp -e "SELECT id, status, moderator_id FROM moderation_tickets;"
```

Expected: `status` `open`, `moderator_id` 0.

Now pick it again and close it as resolved, then check again.

Expected: `status` `resolved`, `moderator_id` 1.

- [ ] **Step 11: Confirm a closed ticket does not come back**

```bash
docker compose -p pixelrp restart emulator && sleep 15
docker compose -p pixelrp logs --since 60s emulator 2>&1 | grep -E "READY|moderation tickets" | tail -3
```

Expected: `Loaded 0 open moderation tickets.` The resolved row stays in the
table as history.

- [ ] **Step 12: Commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402/emulator
git add HabboHotel/Moderation/ModerationManager.cs HabboHotel/Moderation/IModerationManager.cs \
  Communication/Packets/Incoming/Moderation/PickTicketEvent.cs \
  Communication/Packets/Incoming/Moderation/ReleaseTicketEvent.cs \
  Communication/Packets/Incoming/Moderation/CloseTicketEvent.cs \
  Communication/Packets/Incoming/Moderation/CallForHelpPendingCallsDeletedEvent.cs
git commit -m "feat(moderation): write ticket status through on pick, release and close

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Changelog, push and deploy

**Files:**
- Modify: `CHANGELOG.md` (parent repo)
- Modify: the `emulator` submodule pointer (parent repo)

**Interfaces:**
- Consumes: Tasks 1-4 committed on the submodule's `pixelrp` branch.
- Produces: nothing.

- [ ] **Step 1: Push the submodule branch**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402/emulator
git log --oneline -4
git push origin pixelrp
```

Expected: four commits from Tasks 1-4 listed, push succeeds. The main checkout's
copy of the submodule is now behind — mention this in the task report so it can
be pulled there when convenient.

- [ ] **Step 2: Write the changelog entry**

The existing `## 2026-08-14 — Reporting someone actually reaches staff now`
section carries this exact "Known issues" bullet:

```markdown
### Known issues

- Open tickets are still cleared when the hotel restarts, so anything staff
  hasn't picked up before an update is lost. Reports sent after a restart are
  unaffected.
```

Delete that whole `### Known issues` heading and its bullet — it is now fixed.
Then add a new section immediately below the file's maintainer comment block, at
the top of the entries:

```markdown
## 2026-08-14 — Reports wait for staff through a restart

### Fixed

- **Reports no longer vanish when the hotel restarts.** Anything staff hadn't
  picked up or closed yet was thrown away every time the hotel went down for
  an update, so a report sent just before one simply never got looked at. Open
  reports — and ones a staff member has already picked up — now wait through a
  restart, still showing who reported whom, what they said, and the chat lines
  the reporter picked out.

### Known issues

- Closing a report with the mod tool's default-action button does nothing; use
  the ordinary close options instead.
```

- [ ] **Step 3: Commit the changelog and the submodule pointer**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402
git add CHANGELOG.md emulator
git commit -m "fix: bump emulator - moderation tickets survive a restart

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin HEAD
```

- [ ] **Step 4: Merge to main**

The deploy workflow pulls `origin/main` on the VPS, so the work must be on
`main` before deploying. Open a PR from this branch and merge it:

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/.claude/worktrees/magical-swanson-a0f402
gh pr create --fill --base main
```

Then merge it once checks pass (`gh pr merge --squash` or via the UI, whichever
the user prefers — **ask before merging**, this is the point of no return for
production).

- [ ] **Step 5: Deploy**

```bash
gh workflow run deploy.yml
```

Then watch it:

```bash
gh run watch "$(gh run list --workflow=deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

Expected: all steps green, ending on "Polishing pixels" reporting
`Emulator is READY.` The "Applying database patches" step should print
`applying: 22_PersistModerationTickets.sql` — the workflow replays any update
file not yet recorded in the prod `_applied_sql_updates` table. If that line is
absent, the column will be missing on prod and the emulator's inserts will fail;
check that step's log before continuing.

- [ ] **Step 6: Verify on production**

Log in to the live hotel as `Claude` (the prod test account) and send a report,
then confirm from the deploy logs that it persisted. Ask the user to run the
production database check, or run it if VPS access is available in this session:

```bash
ssh root@67.219.109.182 'cd /opt/pixelrp && docker compose -f compose.yaml -f compose.prod.yaml exec -T db sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$MYSQL_DATABASE"'"'"' -e "SHOW COLUMNS FROM moderation_tickets; SELECT id, status, sender_id, reported_id FROM moderation_tickets;"'
```

Expected: `category` and `reported_chats` present, and the test report showing
as one `open` row.

- [ ] **Step 7: Report**

Summarise for the user: what now survives a restart, the `ModeratorInitComposer`
tab fix that came with it, and the dead default-action close button left as a
known issue.

---

## Notes for the implementer

- **Never** run a bare `docker compose -p pixelrp up -d` from this worktree —
  always name the `emulator` service. See the environment setup section.
- SSO tickets are single-use; mint a fresh one for every login.
- `rank` is a reserved word in MySQL 8 — backtick it in every query.
- If a step's expected output does not appear, stop and report rather than
  moving on. Every verification step here is checking a claim the feature rests
  on.
