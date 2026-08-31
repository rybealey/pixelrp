# Working Motto Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On-duty players' mottos read `[WORKING] <corp> · <rank> <tier>` in memory/on the wire only, reverting to the DB motto when the shift ends. Spec: `docs/superpowers/specs/2026-08-31-working-motto-design.md`.

**Architecture:** Emulator-only. All logic in `ShiftManager` (which already owns every shift start/end path): set `Habbo.Motto` in memory + broadcast `UserChangeComposer` on start; reload `users.motto` + re-broadcast on end-with-live-client; do nothing on disconnect (DB never touched). Task 1 implements; Task 2 ships changelog + bump.

**Tech Stack:** C#/.NET 7 Plus emulator, Dapper.

## Global Constraints

- Branch `beta`; `emulator/` is a submodule (branch `pixelrp`) — commit there; root gets changelog + pointer. Do NOT push; controller pushes.
- **First step of Task 1: fast-forward the local emulator to `origin/pixelrp`** (`git -C emulator pull --ff-only`) — a parallel session pushed `e2827cbe` (disconnect-fallback lock) to the same file. Build on top of it.
- Build gate: `docker run --rm -v /Users/rybealey/Documents/Personal/pixelrp/plus/emulator:/src -w /src mcr.microsoft.com/dotnet/sdk:7.0 dotnet build "Plus Emulator.csproj" -c Release` → 0 errors.
- `users.motto` is NEVER written by this feature. No schema, wire, or client changes.
- Motto strings render only in web-font UI; the middot is intentional and allowed HERE (still never in whispers/chat).

---

### Task 1: ShiftManager motto logic

**Files:**
- Modify: `emulator/HabboHotel/Corporations/ShiftManager.cs`

**Interfaces:**
- Consumes: `UserChangeComposer(RoomUser, bool)` — copy the using + the exact self/room broadcast pattern from `HabboHotel/Rooms/Chat/Commands/User/Fun/MimicCommand.cs:52-53`; `Habbo.Motto` (verify it's a settable property; if the setter differs, adapt and report).
- Produces: nothing consumed elsewhere.

- [ ] **Step 1: Fast-forward** — from `emulator/`: `git pull --ff-only` (expect HEAD to become `e2827cbe`). Read the current `ShiftManager.cs` — the lock fix may have adjusted `InterruptForDisconnect(int)`; anchor your edits on the file as it now stands.

- [ ] **Step 2: Extend the StartShift query and session**

Add to the `ShiftSession` class:

```csharp
        // in-memory only: shown on the infostand while on duty; the DB motto
        // is never touched, so disconnect/crash revert for free
        public string WorkingMotto = "";
```

Extend StartShift's job query to also select `r.\`name\` AS RankName, e.\`tier\` AS Tier, r.\`tiers\` AS Tiers` (tuple grows accordingly), and after the session is created build the motto:

```csharp
        var tierSuffix = ((job.Value.Tiers > 0 && job.Value.Tier >= 1)
            ? " " + TierNumerals[Math.Min(job.Value.Tier, TierNumerals.Length) - 1]
            : "");
        session.WorkingMotto = $"[WORKING] {session.CorpName} · {job.Value.RankName}{tierSuffix}";
```

with a class-level `private static readonly string[] TierNumerals = { "I", "II", "III", "IV", "V" };`

- [ ] **Step 3: Add the apply/revert helpers**

```csharp
    // Sets the in-memory motto and pushes it to the infostand (self + room).
    // users.motto is deliberately never written: the DB always holds the real
    // RP-managed motto, so any reload (relog, crash) self-heals.
    private static void ApplyMotto(GameClient client, string motto)
    {
        var habbo = client?.GetHabbo();
        if (habbo == null) return;
        habbo.Motto = motto;
        var room = habbo.CurrentRoom;
        var roomUser = room?.GetRoomUserManager()?.GetRoomUserByHabbo(habbo.Id);
        if (roomUser == null) return;
        client.Send(new UserChangeComposer(roomUser, true));
        room.SendPacket(new UserChangeComposer(roomUser, false));
    }

    private static void RevertMotto(GameClient client)
    {
        var habbo = client?.GetHabbo();
        if (habbo == null) return;
        string motto;
        using (var connection = PlusEnvironment.DatabaseManager.Connection())
            motto = connection.QuerySingleOrDefault<string>(
                "SELECT `motto` FROM `users` WHERE `id` = @userId LIMIT 1", new { userId = habbo.Id }) ?? "";
        ApplyMotto(client, motto);
    }
```

- [ ] **Step 4: Wire the call sites**

- End of `StartShift` (after the on-duty whisper): `ApplyMotto(client, session.WorkingMotto);`
- `StopShift`: after the banking/whisper, `RevertMotto(client);`
- `InterruptForIdle`: after the banking/whisper, `RevertMotto(client);`
- `InterruptForDisconnect(int userId)`: in the branch where a live client WAS resolved (superfire, tick fallback), after its end-session handling: `RevertMotto(client);`
- `InterruptForDisconnect(Habbo habbo)`: NO motto work (connection is going away; DB already holds the real motto).
- The no-room auto-interrupt inside `TickSession` routes through the idle path — confirm it therefore hits `RevertMotto` once, and that a null room inside ApplyMotto (possible there) safely skips the broadcast while still fixing the in-memory value.

- [ ] **Step 5: Build gate** — the docker command from Global Constraints → 0 errors.

- [ ] **Step 6: Commit (emulator repo)**

```bash
git add HabboHotel/Corporations/ShiftManager.cs
git commit -m "feat(corps): working motto while on duty

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Changelog + root bump

**Files:** root `CHANGELOG.md`, `emulator` pointer (and `client` pointer ONLY if the root repo shows it modified — a parallel session may have bumped it; do not touch an unmodified pointer).

- [ ] **Step 1: Changelog** — the top entry is currently `## 2026-08-31 — Clock in, get paid`. Append this bullet to the END of that entry's `### Added` list (same release, same day — do not create a new dated section):

```markdown
- **Wear your shift.** While you're on duty your motto shows it - like
  "[WORKING] San Francisco Police Department · Officer II" - and flips back
  to normal the moment you clock out.
```

- [ ] **Step 2: Commit (root repo)** — from the root: `git pull --ff-only` first (the parallel lock-fix session may have pushed a root bump), then `git add CHANGELOG.md emulator` (plus `client` only if already modified) and commit:

```bash
git commit -m "feat(corps): working motto while on duty (bump emulator)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Do NOT push; the controller pushes emulator then root, and the beta deploy auto-fires.
