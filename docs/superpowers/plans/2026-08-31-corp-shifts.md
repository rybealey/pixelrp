# Corporation Shifts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `:startwork` / `:stopwork` shifts with a persistent 10-minute pay countdown, per-minute countdown whispers, payouts to credits, auto-interrupt (disconnect / idle / superfire), and live-ticking shift counts in the Corporations window and RP profile. Spec: `docs/superpowers/specs/2026-08-31-corp-shifts-design.md`.

**Architecture:** Task 1 builds the emulator core (migration, static `ShiftManager` with a 10s timer, the two commands, three interrupt hooks). Task 2 appends shift fields to the two corp packets (emulator side). Task 3 mirrors those fields in the renderer parsers (stacked yarn patch). Task 4 renders + locally ticks the counts in the client. Task 5 ships changelog + submodule bumps. Emulator and client halves of the wire change land in ONE deploy (tasks are commits, not deploys).

**Tech Stack:** C#/.NET 7 (Plus emulator, Dapper), TypeScript (nitro-renderer via yarn patch, nitro-react), MySQL.

## Global Constraints

- Branch `beta` everywhere; `client/` and `emulator/` are separate submodule repos — commit in each, root repo gets changelog + pointer bumps. Do NOT push; the controller pushes after review.
- Build gates: emulator `docker run --rm -v <repo>/emulator:/src -w /src mcr.microsoft.com/dotnet/sdk:7.0 dotnet build "Plus Emulator.csproj" -c Release` → 0 errors (warnings are pre-existing noise); client `yarn build` from `client/` → no errors. No test suites exist.
- EvaWire discipline: never write undefined/null into a packet; new fields are APPENDED at the end of their payload section; composer and parser field order must match exactly.
- No em-dashes in any client-visible string; plain hyphens. The middot (·) is allowed ONLY in Ubuntu-rendered window text (corps window / profile cards) — NEVER in whispers or chat (Volter font renders it as a music note).
- Renderer patch discipline: stack via `yarn patch -u @nitrots/nitro-renderer` (ambiguous-list → take the LAST locator), verify the extract contains prior customs (`grep RpRoomZoneSaveComposer src/nitro/communication/NitroMessages.ts` ≥ 1) before editing, `yarn patch-commit -s`, `yarn install`, verify no pre-existing patch file changed.
- Pay interval: 600 seconds; pay = the rank's `pay` column (coins), tier never affects pay.
- The client's employment cache key is USER ID (`RpEmploymentRegistry`), never room index.

---

### Task 1: Emulator core — migration, ShiftManager, commands, hooks

**Files:**
- Create: `emulator/Resources/SQLs/Updates/48_CorporationShifts.sql`
- Create: `emulator/HabboHotel/Corporations/ShiftManager.cs`
- Create: `emulator/HabboHotel/Rooms/Chat/Commands/User/StartWorkCommand.cs`
- Create: `emulator/HabboHotel/Rooms/Chat/Commands/User/StopWorkCommand.cs`
- Modify: command registration (locate: `grep -rn "superfire\|SuperFireCommand" emulator/HabboHotel/Rooms/Chat/Commands/` — register the two new commands EXACTLY the way SuperFire/Dnd are registered, same file, no permission row needed)
- Modify: `emulator/HabboHotel/Users/Habbo.cs` (`OnDisconnect`, line ~477)
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs` (idle transition, line ~1281)
- Modify: `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/SuperFireCommand.cs`
- Modify: wherever the emulator initializes pixelrp singletons at boot (locate a spot AFTER the database is ready — e.g. where the Game/PlusEnvironment init calls other managers; grep `DiscordSyncUtility` for precedent) — call `ShiftManager.Init();`

**Interfaces:**
- Consumes: `PlusEnvironment.DatabaseManager.Connection()` (Dapper), `PlusEnvironment.Game.ClientManager.GetClientByUserId(int)`, `GameClient.SendWhisper(string)`, `CreditBalanceComposer` (copy the using from `GiveCommand.cs`, which does `target.Credits += amount; target.Client.Send(new CreditBalanceComposer(target.Credits));`), `UnixTimestamp.GetNow()`.
- Produces (used by Tasks 2): `ShiftManager.IsOnDuty(int userId): bool`, `ShiftManager.LiveSessionSeconds(int userId): int` (seconds elapsed in the CURRENT live session, 0 if off duty), `ShiftManager.StartShift(GameClient)`, `ShiftManager.StopShift(GameClient)`, `ShiftManager.InterruptForIdle(GameClient)`, `ShiftManager.InterruptForDisconnect(int userId)`, `ShiftManager.Init()`.

- [ ] **Step 1: Write the migration**

`emulator/Resources/SQLs/Updates/48_CorporationShifts.sql`:

```sql
-- Shifts: seconds banked toward the CURRENT 10-minute pay interval. Resets
-- on payout (overflow carries). shift_seconds / shift_seconds_week keep the
-- lifetime and weekly totals; on_duty is cleared at boot (stale on crash).

ALTER TABLE `rp_corporation_employees`
  ADD COLUMN `pay_seconds` int NOT NULL DEFAULT 0 AFTER `shift_seconds_week`;
```

- [ ] **Step 2: Write ShiftManager**

`emulator/HabboHotel/Corporations/ShiftManager.cs` — exact content (adjust ONLY the `CreditBalanceComposer` using to match GiveCommand's, and the logger type to whatever neighboring managers use if `NLog` differs):

```csharp
using System.Collections.Concurrent;
using Dapper;
using Plus.HabboHotel.GameClients;
using Plus.Utilities;

namespace Plus.HabboHotel.Corporations;

/// <summary>
/// pixelrp: live shift tracking for :startwork / :stopwork. One in-memory
/// session per on-duty player; a 10-second timer drives minute flushes,
/// countdown whispers and payouts. Progress toward the next pay persists in
/// rp_corporation_employees.pay_seconds, so stopping (or logging out) 3
/// minutes short of payday resumes with 3 minutes left.
/// </summary>
public static class ShiftManager
{
    public const int PayIntervalSeconds = 600;

    private sealed class ShiftSession
    {
        public int UserId;
        public string CorpName = "";
        public int RankPay;
        // pay_seconds already banked in the DB when this session started
        public int BasePaySeconds;
        public double StartedAt;
        // seconds of THIS session already flushed to the DB
        public int FlushedSeconds;
        // payouts already made this session (600s each)
        public int PaidIntervals;
        // last minute boundary we acted on (whisper/flush/pay)
        public int LastMinute;
    }

    private static readonly ConcurrentDictionary<int, ShiftSession> Sessions = new();
    private static System.Threading.Timer _timer;

    public static void Init()
    {
        // stale on-duty flags from a crash; at most ~1 minute of unflushed
        // progress is lost with them
        using (var connection = PlusEnvironment.DatabaseManager.Connection())
            connection.Execute("UPDATE `rp_corporation_employees` SET `on_duty` = 0 WHERE `on_duty` = 1");
        _timer = new System.Threading.Timer(_ => Tick(), null, 10000, 10000);
    }

    public static bool IsOnDuty(int userId) => Sessions.ContainsKey(userId);

    // Live seconds of the current session (0 off duty) - composers add this
    // to the persisted counters so viewers see ticking values.
    public static int LiveSessionSeconds(int userId)
        => Sessions.TryGetValue(userId, out var session) ? Elapsed(session) : 0;

    public static void StartShift(GameClient client)
    {
        var userId = client.GetHabbo().Id;
        if (Sessions.ContainsKey(userId))
        {
            client.SendWhisper("You're already on duty.");
            return;
        }
        (int PaySeconds, int Pay, string CorpName)? job;
        using (var connection = PlusEnvironment.DatabaseManager.Connection())
        {
            job = connection.QuerySingleOrDefault<(int PaySeconds, int Pay, string CorpName)?>(
                "SELECT e.`pay_seconds` AS PaySeconds, r.`pay` AS Pay, c.`name` AS CorpName " +
                "FROM `rp_corporation_employees` e " +
                "INNER JOIN `rp_corporation_ranks` r ON r.`id` = e.`rank_id` " +
                "INNER JOIN `rp_corporations` c ON c.`id` = e.`corporation_id` " +
                "WHERE e.`user_id` = @userId LIMIT 1", new { userId });
            if (job == null)
            {
                client.SendWhisper("You don't have a job. Get hired by a corporation first.");
                return;
            }
            connection.Execute("UPDATE `rp_corporation_employees` SET `on_duty` = 1 WHERE `user_id` = @userId LIMIT 1", new { userId });
        }
        var session = new ShiftSession
        {
            UserId = userId,
            CorpName = job.Value.CorpName,
            RankPay = job.Value.Pay,
            BasePaySeconds = job.Value.PaySeconds,
            StartedAt = UnixTimestamp.GetNow()
        };
        Sessions[userId] = session;
        client.SendWhisper($"You are now on duty at {session.CorpName}. {PayMessage(RemainingSeconds(session, 0))}");
    }

    public static void StopShift(GameClient client)
    {
        var userId = client.GetHabbo().Id;
        if (!Sessions.TryRemove(userId, out var session))
        {
            client.SendWhisper("You're not on duty.");
            return;
        }
        var banked = EndSession(session);
        client.SendWhisper($"Off duty. {FormatMinutes(banked)} banked toward your next pay.");
    }

    public static void InterruptForIdle(GameClient client)
    {
        var userId = client?.GetHabbo()?.Id ?? 0;
        if (userId == 0 || !Sessions.TryRemove(userId, out var session)) return;
        var banked = EndSession(session);
        client.SendWhisper($"Your shift ended because you went idle. {FormatMinutes(banked)} banked toward your next pay.");
    }

    public static void InterruptForDisconnect(int userId)
    {
        if (!Sessions.TryRemove(userId, out var session)) return;
        EndSession(session);
    }

    private static int Elapsed(ShiftSession session)
        => (int)(UnixTimestamp.GetNow() - session.StartedAt);

    // total seconds toward the CURRENT pay interval right now
    private static int PayProgress(ShiftSession session, int elapsed)
        => session.BasePaySeconds + elapsed - (session.PaidIntervals * PayIntervalSeconds);

    private static int RemainingSeconds(ShiftSession session, int elapsed)
        => PayIntervalSeconds - PayProgress(session, elapsed);

    private static string PayMessage(int remainingSeconds)
    {
        var minutes = Math.Max(1, (remainingSeconds + 59) / 60);
        return (minutes == 1) ? "Next pay in 1 minute." : $"Next pay in {minutes} minutes.";
    }

    private static string FormatMinutes(int seconds) => $"{seconds / 60}m";

    // Banks the session into the DB (delta counters, absolute pay_seconds),
    // clears on_duty, returns the banked pay_seconds.
    private static int EndSession(ShiftSession session)
    {
        var elapsed = Elapsed(session);
        var paySeconds = PayProgress(session, elapsed);
        Flush(session, elapsed, paySeconds, offDuty: true);
        return paySeconds;
    }

    private static void Flush(ShiftSession session, int elapsed, int paySeconds, bool offDuty)
    {
        var delta = elapsed - session.FlushedSeconds;
        if (delta < 0) delta = 0;
        session.FlushedSeconds = elapsed;
        using var connection = PlusEnvironment.DatabaseManager.Connection();
        connection.Execute(
            "UPDATE `rp_corporation_employees` SET " +
            "`pay_seconds` = @paySeconds, " +
            "`shift_seconds` = `shift_seconds` + @delta, " +
            "`shift_seconds_week` = `shift_seconds_week` + @delta" +
            (offDuty ? ", `on_duty` = 0" : "") +
            " WHERE `user_id` = @userId LIMIT 1",
            new { paySeconds, delta, userId = session.UserId });
    }

    private static void Tick()
    {
        foreach (var session in Sessions.Values)
        {
            try
            {
                TickSession(session);
            }
            catch
            {
                // one broken session must not stall the others
            }
        }
    }

    private static void TickSession(ShiftSession session)
    {
        var client = PlusEnvironment.Game.ClientManager.GetClientByUserId(session.UserId);
        if (client == null)
        {
            // missed the disconnect hook somehow - bank and drop
            InterruptForDisconnect(session.UserId);
            return;
        }
        var elapsed = Elapsed(session);
        var minute = elapsed / 60;
        if (minute <= session.LastMinute) return;
        session.LastMinute = minute;

        var paidThisMinute = false;
        while (PayProgress(session, elapsed) >= PayIntervalSeconds)
        {
            session.PaidIntervals++;
            paidThisMinute = true;
            client.GetHabbo().Credits += session.RankPay;
            client.Send(new CreditBalanceComposer(client.GetHabbo().Credits));
            client.SendWhisper($"Payday! You earned {session.RankPay}c.");
        }

        Flush(session, elapsed, PayProgress(session, elapsed), offDuty: false);

        if (!paidThisMinute)
            client.SendWhisper(PayMessage(RemainingSeconds(session, elapsed)));
    }
}
```

Add the `using` for `CreditBalanceComposer` copied from `GiveCommand.cs`.

- [ ] **Step 3: Write the two commands**

`emulator/HabboHotel/Rooms/Chat/Commands/User/StartWorkCommand.cs`:

```csharp
using Plus.HabboHotel.Corporations;
using Plus.HabboHotel.GameClients;

namespace Plus.HabboHotel.Rooms.Chat.Commands.User;

/// <summary>
/// pixelrp: :startwork - begin a shift at your corporation. Pay lands every
/// 10 minutes worked; progress persists across sessions.
/// </summary>
internal class StartWorkCommand : IChatCommand
{
    public string Key => "startwork";
    public string PermissionRequired => "";

    public string Parameters => "";

    public string Description => "Start your shift at your corporation.";

    public void Execute(GameClient session, Room room, string[] parameters)
    {
        ShiftManager.StartShift(session);
    }
}
```

`emulator/HabboHotel/Rooms/Chat/Commands/User/StopWorkCommand.cs`: identical shape — Key `stopwork`, Description `End your shift.`, body `ShiftManager.StopShift(session);`, class `StopWorkCommand`, doc comment `:stopwork - end your shift, banking progress toward your next pay.`

If the command interface's `Execute` signature differs (check `DndCommand.cs` — it is `void Execute(GameClient session, Room room, string[] parameters)`), match the real one. If registration is list-based (a `Register("dnd", new DndCommand())` style block), add both commands there; if reflection-based, no registration edit is needed — verify by grepping how `superfire` reaches the `_commands` dictionary. IMPORTANT: `PermissionRequired => ""` means no permission row is required (CommandManager skips the check for empty strings); if the interface forbids empty, mirror whatever an ungated player command uses.

- [ ] **Step 4: Wire the three interrupt hooks + Init**

(a) `emulator/HabboHotel/Users/Habbo.cs`, in `OnDisconnect()` (line ~477), directly after the `if (_disconnected) return;` guard:

```csharp
        Corporations.ShiftManager.InterruptForDisconnect(Id);
```

(b) `emulator/HabboHotel/Rooms/RoomUserManager.cs`, at the idle transition (~line 1281, `user.IsAsleep = true;` followed by `_room.SendPacket(new SleepComposer(user, true));`), directly after the SleepComposer send:

```csharp
                        // pixelrp: going idle ends any active shift (progress banked)
                        if (!user.IsBot && user.GetClient() != null)
                            Corporations.ShiftManager.InterruptForIdle(user.GetClient());
```

Add a `using Plus.HabboHotel.Corporations;` OR use the fully-qualified name as shown — pick whichever matches the file's existing style.

(c) `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/SuperFireCommand.cs`, immediately BEFORE the `DELETE FROM rp_corporation_employees` block:

```csharp
        // end any live shift first - banks progress and clears on_duty
        ShiftManager.InterruptForDisconnect(target.Id);
```

(`using Plus.HabboHotel.Corporations;` already present in that file.)

(d) Call `ShiftManager.Init();` once at boot, after the database is available — put it wherever other pixelrp bootstrapping happens (find the Game/PlusEnvironment init sequence; anywhere after DatabaseManager is connected and before/with the game loop starting is fine).

- [ ] **Step 5: Build gate**

`docker run --rm -v /Users/rybealey/Documents/Personal/pixelrp/plus/emulator:/src -w /src mcr.microsoft.com/dotnet/sdk:7.0 dotnet build "Plus Emulator.csproj" -c Release 2>&1 | tail -4`
Expected: `0 Error(s)`.

- [ ] **Step 6: Commit (emulator repo)**

```bash
git add Resources/SQLs/Updates/48_CorporationShifts.sql HabboHotel/Corporations/ShiftManager.cs HabboHotel/Rooms/Chat/Commands/User/StartWorkCommand.cs HabboHotel/Rooms/Chat/Commands/User/StopWorkCommand.cs HabboHotel/Users/Habbo.cs HabboHotel/Rooms/RoomUserManager.cs HabboHotel/Rooms/Chat/Commands/Moderator/SuperFireCommand.cs
git add -u
git commit -m "feat(corps): shifts - :startwork/:stopwork, persistent pay countdown, payouts

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Emulator wire — append shift fields to both corp packets

**Files:**
- Modify: `emulator/Communication/Packets/Outgoing/Users/RpCorpDetailComposer.cs`
- Modify: `emulator/Communication/Packets/Incoming/Users/RpGetCorpDetailEvent.cs`
- Modify: `emulator/Communication/Packets/Outgoing/Users/RpUserCorpComposer.cs`
- Modify: `emulator/HabboHotel/Corporations/CorporationUtility.cs`
- Modify: every `new RpUserCorpComposer(` call-site (`grep -rn "new RpUserCorpComposer" emulator/`)

**Interfaces:**
- Consumes: `ShiftManager.IsOnDuty(userId)`, `ShiftManager.LiveSessionSeconds(userId)` from Task 1.
- Produces (wire contract Task 3 mirrors EXACTLY): `RpCorpDetail` employee payload order becomes `username, figure, tier, online, onDuty, shiftSeconds, shiftSecondsWeek` (two ints APPENDED). `RpUserCorp` payload order becomes `userId, corpId, badge, corpName, rankName, tier, shiftSeconds, shiftSecondsWeek, onDuty` (three ints APPENDED).

- [ ] **Step 1: RpCorpDetailComposer**

Extend the `Employee` record: `public record Employee(string Username, string Figure, int Tier, bool Online, bool OnDuty, int ShiftSeconds, int ShiftSecondsWeek);` and append inside the employee write loop, after the OnDuty write:

```csharp
                packet.WriteInteger(employee.ShiftSeconds);
                packet.WriteInteger(employee.ShiftSecondsWeek);
```

- [ ] **Step 2: RpGetCorpDetailEvent**

Extend the employees query with `e.\`shift_seconds\` AS ShiftSeconds, e.\`shift_seconds_week\` AS ShiftSecondsWeek` (tuple gains `int ShiftSeconds, int ShiftSecondsWeek`), and build employees as:

```csharp
                .Select(employee => new RpCorpDetailComposer.Employee(
                    employee.Username, employee.Figure, employee.Tier,
                    _clientManager.GetClientByUserId(employee.UserId) != null,
                    ShiftManager.IsOnDuty(employee.UserId),
                    employee.ShiftSeconds + ShiftManager.LiveSessionSeconds(employee.UserId),
                    employee.ShiftSecondsWeek + ShiftManager.LiveSessionSeconds(employee.UserId)))
```

Note `OnDuty` now comes from `ShiftManager.IsOnDuty` (live truth) instead of the DB flag — the DB flag remains for crash hygiene. Add `using Plus.HabboHotel.Corporations;` if missing.

- [ ] **Step 3: RpUserCorpComposer + CorporationUtility + call-sites**

`RpUserCorpComposer`: constructor gains `int shiftSeconds, int shiftSecondsWeek, bool onDuty`; store and append at the END of `Compose`:

```csharp
        packet.WriteInteger(_shiftSeconds);
        packet.WriteInteger(_shiftSecondsWeek);
        packet.WriteInteger(_onDuty ? 1 : 0);
```

`CorporationUtility`: extend the `Employment` record with `int ShiftSeconds, int ShiftSecondsWeek`; add `e.\`shift_seconds\` AS ShiftSeconds, e.\`shift_seconds_week\` AS ShiftSecondsWeek` to BOTH queries; `ComposeFor` becomes:

```csharp
    public static RpUserCorpComposer ComposeFor(int userId, Employment employment)
    {
        if (employment == null || employment.CorpId == 0)
            return new RpUserCorpComposer(userId, 0, "", "", "", 0, 0, 0, false);
        var live = ShiftManager.LiveSessionSeconds(userId);
        return new RpUserCorpComposer(employment.UserId, employment.CorpId, employment.Badge, employment.CorpName, employment.RankName, employment.Tier,
            employment.ShiftSeconds + live, employment.ShiftSecondsWeek + live, ShiftManager.IsOnDuty(userId));
    }
```

Fix every other `new RpUserCorpComposer(` call-site to route through `ComposeFor` where possible, else pass explicit values (unemployed clears use `0, 0, false`).

- [ ] **Step 4: Build gate + commit (emulator repo)**

Same docker build as Task 1 → 0 errors. Then:

```bash
git add -u
git commit -m "feat(corps): shift seconds + live on-duty state on the corp packets

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Renderer parsers — mirror the appended fields (stacked patch)

**Files:**
- Modify (via `yarn patch -u` workflow in `client/`): `.yarn/patches/` (new stacked patch), `package.json`, `yarn.lock`
- Patched files: `src/nitro/communication/messages/incoming/RpCorpDetailEvent.ts`, `src/nitro/communication/messages/incoming/RpUserCorpEvent.ts`

**Interfaces:**
- Consumes: the wire contract from Task 2 (field orders listed there — mirror EXACTLY).
- Produces (Task 4 consumes): `RpCorpDetailParser`'s employee objects gain `shiftSeconds: number` and `shiftSecondsWeek: number`; `RpUserCorpParser` gains getters `shiftSeconds`, `shiftSecondsWeek`, `onDuty: boolean`.

- [ ] **Step 1: Open the stack for update** — `yarn install`, then `yarn patch -u @nitrots/nitro-renderer` (take the LAST locator from the ambiguous list, quoted), verify the extract contains `RpRoomZoneSaveComposer` in `src/nitro/communication/NitroMessages.ts` before editing.

- [ ] **Step 2: RpUserCorpEvent.ts** — in `RpUserCorpParser`: add private fields `_shiftSeconds: number`, `_shiftSecondsWeek: number`, `_onDuty: boolean`; reset them in `flush()` (0/0/false); in `parse()` append AFTER `this._tier = wrapper.readInt();`:

```typescript
        this._shiftSeconds = wrapper.readInt();
        this._shiftSecondsWeek = wrapper.readInt();
        this._onDuty = (wrapper.readInt() === 1);
```

Add getters `shiftSeconds`, `shiftSecondsWeek`, `onDuty` following the file's existing getter style.

- [ ] **Step 3: RpCorpDetailEvent.ts** — find the employee-parsing loop (it reads `username, figure, tier, online, onDuty` per employee) and append two reads per employee, storing them on the employee object as `shiftSeconds` and `shiftSecondsWeek`:

```typescript
            shiftSeconds: wrapper.readInt(),
            shiftSecondsWeek: wrapper.readInt(),
```

(match the file's existing object-literal or class style; if employees are a typed interface in the same file, extend the interface with both numbers).

- [ ] **Step 4: Seal + verify + build** — `yarn patch-commit -s <dir>`, `yarn install`, verify: new patch file only touches the two event files; prior patches untouched; `grep shiftSecondsWeek node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/incoming/RpUserCorpEvent.ts` hits. Then `yarn build` → green. (The client sources don't reference the new fields yet — that's Task 4.)

- [ ] **Step 5: Commit (client repo)**

```bash
git add .yarn/patches package.json yarn.lock
git commit -m "feat(renderer): shift seconds + on-duty on the corp parsers

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Client — live-ticking shift counts (corps window + profile)

**Files:**
- Modify: `client/src/api/rp-employment/RpEmploymentRegistry.ts`
- Modify: the consumer that feeds the registry from `RpUserCorpEvent` (`grep -rn "RpUserCorpEvent" client/src` — extend its `SetRpEmployment` call with the new parser fields)
- Modify: `client/src/components/rp-corporations/RpCorporationsView.tsx` + `.scss`
- Modify: `client/src/components/rp-profile/RpProfileView.tsx` + `.scss`

**Interfaces:**
- Consumes: Task 3's parser fields.
- Produces: a shared formatter — add to `RpEmploymentRegistry.ts`:

```typescript
// "47m" under an hour, then "12h 3m" - minutes granularity everywhere
export const FormatShiftTime = (seconds: number): string =>
{
    const minutes = Math.floor(seconds / 60);

    if(minutes < 60) return `${ minutes }m`;

    return `${ Math.floor(minutes / 60) }h ${ minutes % 60 }m`;
}
```

- [ ] **Step 1: Registry** — extend `RpEmployment` with `shiftSeconds: number; shiftSecondsWeek: number; onDuty: boolean; receivedAt: number;`. In `SetRpEmployment`, stamp `receivedAt: Date.now()` (accept it as part of the passed object or assign before storing — keep the existing signature by having callers include it). Update the registry-feeding event handler to pass the three new parser fields plus `receivedAt: Date.now()`.

- [ ] **Step 2: Corps window** — in `RpCorporationsView.tsx`:
  - When the detail packet arrives, also store `receivedAt: Date.now()` alongside the detail state.
  - Add a minute ticker active only while the window is visible AND any shown employee is on duty:

```tsx
    const [ tickNow, setTickNow ] = useState(Date.now());

    useEffect(() =>
    {
        if(!isVisible) return;

        const interval = setInterval(() => setTickNow(Date.now()), 60000);

        return () => clearInterval(interval);
    }, [ isVisible ]);
```

  - Card stat line: replace the hardcoded `'Weekly: 0'` / `'Total: 0'` with real values; for an on-duty employee add the elapsed seconds since the packet arrived:

```tsx
    const liveExtra = (employee.onDuty ? Math.floor((tickNow - detailReceivedAt) / 1000) : 0);
    // ...
    { [ showWeekly && `Weekly: ${ FormatShiftTime(employee.shiftSecondsWeek + liveExtra) }`, showTotal && `Total: ${ FormatShiftTime(employee.shiftSeconds + liveExtra) }` ].filter(Boolean).join(' · ') }
```

  (Adapt variable names to the component; `tickNow` must be read in the card render so the interval re-renders it. Keep the middot separator — this is Ubuntu-rendered window text.)

- [ ] **Step 3: Profile** — in `RpProfileView.tsx`, inside the employment card (the block rendering `rp-profile-org-name` / `rp-profile-org-role`), add beneath the role line, only when employed:

```tsx
    { employment &&
        <div className="rp-profile-org-shifts">
            { employment.onDuty && <span className="rp-profile-org-onduty" /> }
            { `Weekly: ${ FormatShiftTime(employment.shiftSecondsWeek + profileLiveExtra) } · Total: ${ FormatShiftTime(employment.shiftSeconds + profileLiveExtra) }` }
        </div> }
```

with `profileLiveExtra = (employment?.onDuty ? Math.floor((tickNow - employment.receivedAt) / 1000) : 0)` and the same 60s `tickNow` interval pattern (active while the profile is open). SCSS (`RpProfileView.scss`), matching the org-role styling:

```scss
    .rp-profile-org-shifts {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 10px;
        color: rgba(0, 0, 0, 0.45);
    }

    // matches the corps window's on-duty blue
    .rp-profile-org-onduty {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #2f7fd6;
        flex-shrink: 0;
    }
```

- [ ] **Step 4: Build gate + commit (client repo)**

`yarn build` → green. Then:

```bash
git add src/api/rp-employment src/components/rp-corporations src/components/rp-profile
git add -u
git commit -m "feat(corps): live shift counts on employee cards and profiles

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Changelog + submodule bumps

**Files:**
- Modify: root `CHANGELOG.md`, `client` + `emulator` submodule pointers

**Interfaces:** consumes the committed HEADs from Tasks 2 (emulator) and 4 (client).

- [ ] **Step 1: Changelog** — insert immediately after the maintainer comment block's closing `-->`, above the current top entry:

```markdown
## 2026-08-31 — Clock in, get paid

### Added

- **Shifts are live.** If you have a job, type :startwork to clock in and
  :stopwork to clock out. Every 10 minutes on the clock pays your rank's
  wage straight into your coins, with a whisper each minute counting down
  to payday.
- **Your progress never resets.** Clock out (or log off) 3 minutes before
  payday and you'll be 3 minutes from payday when you clock back in. Going
  idle clocks you out automatically and banks your time.
- **Watch people work.** Employee cards in the Corporations window and the
  job card on profiles now show real weekly and lifetime shift time - and
  they tick up live while someone is on duty.
```

- [ ] **Step 2: Commit (root repo)**

```bash
git add CHANGELOG.md client emulator
git commit -m "feat(corps): shift system - work, countdown, payouts (bump client + emulator)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Do NOT push. Controller pushes client + emulator first, then root; deploy-beta auto-fires and applies the SQL migration; user tests in-game per the spec's verification list.
