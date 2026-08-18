# Walk Responsiveness & Smoothness Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make click-to-walk respond instantly and glide smoothly by removing Nagle batching, drift in the walk-step cadence, the instant-step cooldown hole, and the client's rigid tile animation window.

**Architecture:** Four server changes in the PlusEMU emulator (socket option, two timing constants/loops, one scheduling extension to the existing instant-first-step system) plus one constant change in the nitro-renderer shipped as a hunk in the existing yarn patch. No new subsystems; every change rides existing code paths and the existing `pathfinder.instant.first.step.disabled` kill switch.

**Tech Stack:** C# (.NET, PlusEMU, NetCoreServer 7.0.0), TypeScript (`@nitrots/nitro-renderer@1.6.6` via Yarn 4 patch), Docker builds.

**Spec:** `docs/superpowers/specs/2026-08-18-walk-responsiveness-design.md`

## Global Constraints

- Emulator submodule `emulator/` is on branch `pixelrp` (repo `rybealey/PlusEMU`); client submodule `client/` on branch `pixelrp` (repo `rybealey/nitro-react`); parent repo branch `main`.
- Walk speed must remain exactly one tile per 500ms — no change may let a user move faster.
- The kill switch `server_settings` key `pathfinder.instant.first.step.disabled` = `1` must fully restore today's tick-driven behavior for the self-pace/instant/scheduling features (components 2 and 4). `SettingsManager.TryGetValue` returns `"0"` for missing keys, so absence = enabled.
- The emulator has **no test project** (`Tests/` contains only stale `bin`/`obj`). Verification = clean build + live in-game testing by the user (standing preference: hand off for manual in-game testing; do not screenshot-drive the client).
- The renderer yarn patch must be resealed with the `yarn patch` → copy files → `yarn patch-commit -s` flow, and ALL hunks must be verified present before committing (**7 files** after this work: `AvatarImage.ts`, `AvatarImagePartContainer.ts`, `AvatarImageCache.ts`, `RoomVisualization.ts`, `RoomEngine.ts`, `RoomObjectEventHandler.ts`, `MovingObjectLogic.ts`). The temp dir from `yarn patch` is PRISTINE — it does not contain the existing patch's changes.
- Every player-facing change gets a `CHANGELOG.md` entry (player-facing wording only).
- Emulator build check: `docker compose build emulator` from the repo root (`/Users/rybealey/Documents/Personal/pixelrp/plus`). Client build: `docker/nitro/build-client.sh`.
- Deploys go through `gh workflow run deploy.yml` (never manual SSH).

---

### Task 1: Server constants — socket NoDelay + tighter game loop

**Files:**
- Modify: `emulator/Communication/Abstractions/WebsocketGameServer.cs:17-24` (constructor)
- Modify: `emulator/HabboHotel/Game.cs:44` (`_cycleSleepTime`)

**Interfaces:**
- Consumes: `NetCoreServer.TcpServer.OptionNoDelay` (public bool property inherited by `WsServer`; accepted sessions apply it to their sockets).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Set `OptionNoDelay` in the game-server constructor**

In `emulator/Communication/Abstractions/WebsocketGameServer.cs`, the constructor currently reads:

```csharp
    protected WebsocketGameServer(IOptions<TGameServerOptions> options,
        IGameClientFactory<WsSessionProxy, WsServer> clientFactory,
        IPacketManager packetManager) : base(options.Value.Hostname,
        options.Value.Port)
    {
        _clientFactory = clientFactory;
        _packetManager = packetManager;
    }
```

Change the body to:

```csharp
    protected WebsocketGameServer(IOptions<TGameServerOptions> options,
        IGameClientFactory<WsSessionProxy, WsServer> clientFactory,
        IPacketManager packetManager) : base(options.Value.Hostname,
        options.Value.Port)
    {
        // pixelrp: disable Nagle's algorithm on accepted sessions. The game sends
        // many tiny packets (per-step "mv" statuses, chat); letting the kernel
        // batch them adds tens of ms of latency and jitter to every update.
        OptionNoDelay = true;
        _clientFactory = clientFactory;
        _packetManager = packetManager;
    }
```

- [ ] **Step 2: Tighten the game loop poll**

In `emulator/HabboHotel/Game.cs`, line 44 currently reads:

```csharp
    private readonly int _cycleSleepTime = 25;
```

Change to:

```csharp
    // pixelrp: 5ms poll so the 500ms room tick fires within ~5ms of due time
    // instead of up to 25ms late (walking bots and tick-paced movement stutter
    // by exactly that lateness). GameClientManager.OnCycle is safe at this
    // rate: TestClientConnections self-gates on a 30s stopwatch and
    // HandleTimeouts early-returns on an empty queue.
    private readonly int _cycleSleepTime = 5;
```

- [ ] **Step 3: Build to verify**

Run (from `/Users/rybealey/Documents/Personal/pixelrp/plus`):
```bash
docker compose build emulator 2>&1 | tail -5
```
Expected: build completes with no errors. (This also proves `OptionNoDelay` exists on the `WsServer` base — a typo would be a compile error.)

- [ ] **Step 4: Commit (emulator submodule)**

```bash
git -C emulator add Communication/Abstractions/WebsocketGameServer.cs HabboHotel/Game.cs
git -C emulator commit -m "perf: disable Nagle on game sockets + 5ms game-loop poll

Small per-step mv/status packets were being batched by the kernel (no
TCP_NODELAY), and the 500ms room tick fired up to 25ms late off the 25ms
sleep poll. Both added latency/jitter to every walk step.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Metronome self-pacing + cooldown-hole scheduling

**Files:**
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs:645-709` (`TryInstantFirstStep` + `SelfPaceWalk`)

**Interfaces:**
- Consumes: existing `ProcessUserMovement(RoomUser, List<RoomUser>, out bool)`, `SerializeStatusUpdates()`, `IsValid(RoomUser)`, `_cycleLock`, `RoomUser.SelfPaced` / `IsWalking` / `SetStep` / `PathRecalcNeeded` / `LastInstantStep` fields — all unchanged.
- Produces: `SelfPaceWalk(RoomUser user, int firstBeatDelayMs, bool allowPreWalkFirstBeat)` (private; only called from `TryInstantFirstStep`). Task 4 relies on no signature here — behavior only.

- [ ] **Step 1: Replace `TryInstantFirstStep` and `SelfPaceWalk`**

In `emulator/HabboHotel/Rooms/RoomUserManager.cs`, the two methods currently read (lines 645–709):

```csharp
    // pixelrp instant-first-step: emit a standing unit's first walk step the
    // instant the click arrives instead of waiting up to 500ms for the next
    // room tick. Subsequent steps stay on the tick, so walk SPEED is unchanged.
    // Serialized against the tick via _cycleLock. Kill switch: server_settings
    // key `pathfinder.instant.first.step.disabled` = 1. Cooldown guarantees a
    // click can never produce more than one tile per 500ms.
    public void TryInstantFirstStep(RoomUser user)
    {
        if (PlusEnvironment.SettingsManager.TryGetValue("pathfinder.instant.first.step.disabled") == "1") return;
        if (user == null || user.IsBot) return;
        lock (_cycleLock)
        {
            if (!IsValid(user)) return;
            if (user.IsWalking || user.SetStep) return;      // already moving: tick owns it
            if (!user.PathRecalcNeeded) return;              // no pending request
            if ((DateTime.Now - user.LastInstantStep).TotalMilliseconds < 450) return; // rate cap
            var throwaway = new List<RoomUser>();
            ProcessUserMovement(user, throwaway, out _);      // pathfind + emit first step
            user.LastInstantStep = DateTime.Now;
            SerializeStatusUpdates();                          // push the "mv" status now
            if (user.IsWalking && !user.SelfPaced)
            {
                user.SelfPaced = true;
                _ = SelfPaceWalk(user);   // fire-and-forget beat; coordinates via _cycleLock
            }
        }
    }

    // pixelrp self-paced walk: after an instant first step, drive THIS unit's
    // remaining steps on its own 500ms beat so they are evenly spaced from the
    // instant step instead of snapping to the shared room-tick phase. The
    // global tick skips a SelfPaced unit's movement (see OnCycle), so the two
    // never double-step; both take _cycleLock. Ends when the unit stops,
    // arrives, or leaves — handing movement back to the global tick.
    private async Task SelfPaceWalk(RoomUser user)
    {
        try
        {
            while (true)
            {
                await Task.Delay(500);
                lock (_cycleLock)
                {
                    if (user == null || !IsValid(user) || !user.SelfPaced || !user.IsWalking)
                    {
                        if (user != null) user.SelfPaced = false;
                        return;
                    }
                    var removed = false;
                    ProcessUserMovement(user, new List<RoomUser>(), out removed);
                    SerializeStatusUpdates();
                    if (removed || !user.IsWalking)
                    {
                        user.SelfPaced = false;
                        return;
                    }
                }
            }
        }
        catch (Exception e)
        {
            try { user.SelfPaced = false; } catch { }
            ExceptionLogger.LogException(e);
        }
    }
```

Replace BOTH methods with:

```csharp
    // pixelrp instant-first-step: emit a standing unit's first walk step the
    // instant the click arrives instead of waiting up to 500ms for the next
    // room tick. Subsequent steps stay on a per-user metronome beat, so walk
    // SPEED is unchanged. Serialized against the tick via _cycleLock. Kill
    // switch: server_settings key `pathfinder.instant.first.step.disabled` = 1.
    // A click inside the 450ms cooldown no longer falls back to the (late)
    // global tick — it is scheduled at exactly lastStep + 500ms instead, so
    // responsiveness stays consistent while the speed cap holds.
    public void TryInstantFirstStep(RoomUser user)
    {
        if (PlusEnvironment.SettingsManager.TryGetValue("pathfinder.instant.first.step.disabled") == "1") return;
        if (user == null || user.IsBot) return;
        lock (_cycleLock)
        {
            if (!IsValid(user)) return;
            if (user.IsWalking || user.SetStep) return;      // already moving: its beat owns it
            if (!user.PathRecalcNeeded) return;              // no pending request
            var sinceLastMs = (DateTime.Now - user.LastInstantStep).TotalMilliseconds;
            if (sinceLastMs < 450)
            {
                // Rate-capped: schedule the first step at exactly lastStep + 500ms
                // via the self-pace loop instead of leaving it to the global tick.
                if (!user.SelfPaced)
                {
                    user.SelfPaced = true;
                    _ = SelfPaceWalk(user, Math.Max(1, 500 - (int)sinceLastMs), true);
                }
                return;
            }
            var throwaway = new List<RoomUser>();
            ProcessUserMovement(user, throwaway, out _);      // pathfind + emit first step
            user.LastInstantStep = DateTime.Now;
            SerializeStatusUpdates();                          // push the "mv" status now
            if (user.IsWalking && !user.SelfPaced)
            {
                user.SelfPaced = true;
                _ = SelfPaceWalk(user, 500, false);   // fire-and-forget beat; coordinates via _cycleLock
            }
        }
    }

    // pixelrp self-paced walk: after an instant first step, drive THIS unit's
    // remaining steps on a metronome anchored to the instant step — beat n is
    // due at firstBeatDelayMs + (n-1)*500 on a monotonic clock, so processing
    // time and timer slop never accumulate and steps reach the client evenly
    // spaced (its per-tile animation is a fixed window; late steps = stutter).
    // The global tick skips a SelfPaced unit's movement (see OnCycle), so the
    // two never double-step; both take _cycleLock. Ends when the unit stops,
    // arrives, or leaves — handing movement back to the global tick.
    // allowPreWalkFirstBeat: the first beat may fire for a unit that is not
    // walking yet but has a pending PathRecalcNeeded (the rate-capped click) —
    // that beat pathfinds and emits the first step itself.
    private async Task SelfPaceWalk(RoomUser user, int firstBeatDelayMs, bool allowPreWalkFirstBeat)
    {
        try
        {
            var clock = System.Diagnostics.Stopwatch.StartNew();
            var beat = 0;
            while (true)
            {
                beat++;
                var dueMs = firstBeatDelayMs + (beat - 1) * 500L;
                var waitMs = dueMs - clock.ElapsedMilliseconds;
                if (waitMs > 0) await Task.Delay((int)waitMs);
                lock (_cycleLock)
                {
                    if (user == null || !IsValid(user) || !user.SelfPaced)
                    {
                        if (user != null) user.SelfPaced = false;
                        return;
                    }
                    var preWalkStart = allowPreWalkFirstBeat && beat == 1
                        && !user.IsWalking && user.PathRecalcNeeded;
                    if (!user.IsWalking && !preWalkStart)
                    {
                        user.SelfPaced = false;
                        return;
                    }
                    var removed = false;
                    ProcessUserMovement(user, new List<RoomUser>(), out removed);
                    if (preWalkStart) user.LastInstantStep = DateTime.Now;
                    SerializeStatusUpdates();
                    if (removed || !user.IsWalking)
                    {
                        user.SelfPaced = false;
                        return;
                    }
                }
            }
        }
        catch (Exception e)
        {
            try { user.SelfPaced = false; } catch { }
            ExceptionLogger.LogException(e);
        }
    }
```

Behavior notes for the implementer (all follow from the code above — do not add extra logic):
- A second click during a pending pre-walk beat just updates `GoalX`/`GoalY` via `MoveTo` and returns (`user.SelfPaced` already true); the pending beat uses the latest goal.
- If the pre-walk beat finds no valid path (`ProcessUserMovement` leaves `IsWalking` false), the loop exits and resets `SelfPaced` — the same as arriving.
- The kill switch check at the top of `TryInstantFirstStep` disables both the instant step AND the scheduling, restoring pure tick behavior.

- [ ] **Step 2: Build to verify**

Run (from `/Users/rybealey/Documents/Personal/pixelrp/plus`):
```bash
docker compose build emulator 2>&1 | tail -5
```
Expected: build completes with no errors.

- [ ] **Step 3: Restart the local emulator and hand off for a feel test**

Run:
```bash
docker compose up -d emulator && sleep 8 && docker compose logs emulator --tail 5
```
Expected: emulator boots to READY. Then mint an SSO ticket for the local Admin account (id 1) and hand the URL to the user:

```bash
TICKET="PixelRP-$(uuidgen)"
docker exec pixelrp-db-1 sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "UPDATE users SET auth_ticket = '"'"''"$TICKET"''"'"' WHERE id = 1;"'
echo "http://localhost:8080/nitro-assets/client/index.html?sso=$TICKET"
```

Ask the user to feel-test locally: standing click (instant start), long walk (even glide), rapid mid-walk redirects (course change at the tile boundary), rapid single-tile hops (consistent ~500ms cadence, never a ~1s hiccup).

- [ ] **Step 4: Commit (emulator submodule)**

```bash
git -C emulator add HabboHotel/Rooms/RoomUserManager.cs
git -C emulator commit -m "perf: metronome self-paced walk beats + schedule rate-capped clicks

SelfPaceWalk now fires beat n at t0 + n*500ms on a monotonic clock instead
of sleeping 500ms after each beat's processing, so steps stop drifting late
(the client's fixed 500ms tile animation turned that drift into a visible
stutter at every tile boundary). Clicks landing inside the 450ms instant-step
cooldown are scheduled at exactly lastStep + 500ms instead of falling back
to the global tick (up to ~525ms late). Walk speed unchanged; kill switch
pathfinder.instant.first.step.disabled still restores tick behavior.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Client glide — renderer patch reseal

**Files:**
- Modify: `client/node_modules/@nitrots/nitro-renderer/src/nitro/room/object/logic/MovingObjectLogic.ts:7`
- Modify (regenerated): `client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch`
- Modify (auto): `client/yarn.lock`

**Interfaces:**
- Consumes: nothing from other tasks (independent of server changes).
- Produces: nothing later tasks depend on beyond the built client bundle.

- [ ] **Step 1: Edit the working copy in node_modules**

In `client/node_modules/@nitrots/nitro-renderer/src/nitro/room/object/logic/MovingObjectLogic.ts`, line 7 currently reads:

```typescript
    public static DEFAULT_UPDATE_INTERVAL: number = 500;
```

Change to:

```typescript
    // PixelRP: 515 (was 500). The server emits walk steps every 500ms; animating
    // each tile over slightly longer means normal network jitter lands inside the
    // animation window instead of freezing the avatar at the tile edge. The lerp
    // restarts from the current rendered position on each update, so the ~15ms
    // never accumulates.
    public static DEFAULT_UPDATE_INTERVAL: number = 515;
```

- [ ] **Step 2: Reseal the yarn patch (full 7-file flow)**

Run (from `/Users/rybealey/Documents/Personal/pixelrp/plus/client`):
```bash
corepack yarn patch '@nitrots/nitro-renderer@npm:1.6.6' 2>&1 | grep "edit the following"
```
This prints a pristine temp dir path (call it `$TMP`). Then copy ALL modified files into it and verify each:
```bash
TMP=<paste the printed path>
NM=node_modules/@nitrots/nitro-renderer
for f in \
  src/nitro/avatar/AvatarImage.ts \
  src/nitro/avatar/AvatarImagePartContainer.ts \
  src/nitro/avatar/cache/AvatarImageCache.ts \
  src/nitro/room/object/visualization/room/RoomVisualization.ts \
  src/nitro/room/RoomEngine.ts \
  src/nitro/room/RoomObjectEventHandler.ts \
  src/nitro/room/object/logic/MovingObjectLogic.ts ; do
  cp "$NM/$f" "$TMP/$f" && echo "copied $f"
done
grep -c "DEFAULT_UPDATE_INTERVAL: number = 515" "$TMP/src/nitro/room/object/logic/MovingObjectLogic.ts"
grep -c "__pixelrpClickthrough" "$TMP/src/nitro/room/RoomEngine.ts" "$TMP/src/nitro/room/RoomObjectEventHandler.ts"
grep -c "texture.destroy(true)" "$TMP/src/nitro/avatar/AvatarImage.ts"
```
Expected: 7 "copied" lines; each grep returns 1 (per file).

Commit the patch and verify all 7 files landed:
```bash
corepack yarn patch-commit -s "$TMP"
grep -E "^diff --git" .yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch
```
Expected: exactly 7 `diff --git` lines — the 6 existing files plus `src/nitro/room/object/logic/MovingObjectLogic.ts`.

- [ ] **Step 3: Verify the patch re-applies cleanly**

```bash
corepack yarn install 2>&1 | tail -3
grep -c "= 515" node_modules/@nitrots/nitro-renderer/src/nitro/room/object/logic/MovingObjectLogic.ts
```
Expected: install completes; grep returns 1.

- [ ] **Step 4: Build the client**

Run (from `/Users/rybealey/Documents/Personal/pixelrp/plus`):
```bash
docker/nitro/build-client.sh 2>&1 | tail -3
```
Expected: "Done. nginx serves nitro/client/ at /nitro-assets/client/."

- [ ] **Step 5: Commit (client submodule)**

```bash
git -C client add -A
git -C client commit -m "perf: stretch tile animation window 500->515ms (glide over jitter)

The server emits walk steps every 500ms and the client animated each tile
over exactly 500ms, so any packet jitter froze the avatar at the tile edge.
Slightly outlasting the beat absorbs the jitter; the lerp restarts from the
current rendered position each update, so the lag never accumulates.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Changelog, ship, and hand off

**Files:**
- Modify: `CHANGELOG.md` (top of file, below the maintainer comment)
- Modify: parent repo gitlinks for `emulator` and `client`

**Interfaces:**
- Consumes: committed emulator (Tasks 1–2) and client (Task 3) submodules.
- Produces: deployed prod.

- [ ] **Step 1: Add the CHANGELOG entry**

Insert above the current topmost `##` entry in `CHANGELOG.md`:

```markdown
## 2026-08-18 — Snappier, smoother walking

### Changed

- **Walking responds faster and glides more smoothly.** Your avatar sets off
  the moment you click, steps flow evenly instead of hitching at each tile,
  and changing direction mid-walk takes effect right at the tile boundary —
  even during rapid clicking.
```

- [ ] **Step 2: Commit submodule bumps + changelog, push everything**

Run (from `/Users/rybealey/Documents/Personal/pixelrp/plus`):
```bash
git -C emulator push origin pixelrp
git -C client push origin pixelrp
git add CHANGELOG.md emulator client
git commit -m "perf: bump emulator+client - walk responsiveness & smoothness pass

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

- [ ] **Step 3: Deploy and watch**

```bash
gh workflow run deploy.yml && sleep 6 && rid=$(gh run list --workflow=deploy.yml --limit 1 --json databaseId -q '.[0].databaseId') && gh run watch "$rid" --exit-status 2>&1 | tail -2 && gh run view "$rid" --json status,conclusion -q '.status + " / " + .conclusion' && curl -s -o /dev/null -w "prod: %{http_code}\n" https://pixelrp.co/
```
Expected: `completed / success`, `prod: 200`.

- [ ] **Step 4: Hand off for prod feel test**

Tell the user to test on prod: standing click, long walk, rapid mid-walk redirects, rapid single-tile hops — and that `server_settings` key `pathfinder.instant.first.step.disabled` = `1` (+ emulator restart) rolls the walk behavior back to the old tick pacing if anything feels wrong (Nagle/tick/glide constants stay, which are strictly beneficial).
