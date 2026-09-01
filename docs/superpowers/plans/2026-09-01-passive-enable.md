# Passive Enable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every player in passive state (`RpPassiveSeconds > 0`) the custom `Passive_Enable.nitro` avatar effect, and auto-remove it the moment they leave passive.

**Architecture:** Register the bundle as effect id `248`. A per-tick helper in `RoomUserManager` treats the enable as a resuming *baseline* — asserted only when the effect slot is free, yielding to dance/ride/tile/item effects and coming back when they end. Four lifecycle-edge call sites apply/clear it immediately (no visible pop); the tick is the safety net.

**Tech Stack:** C# / .NET 7 (Arcturus-derived emulator, single solution `emulator/Plus Emulator.sln`), Nitro asset bundles, `EffectMap.json` gamedata.

## Global Constraints

- **No automated test harness exists** for the emulator (no test project). The per-task gate is a clean `dotnet build`; behavioral verification is the manual in-game matrix in Task 5 (house style: Ry tests in-game).
- **Effect id is `248`** — ids currently run 1–247 with no gaps.
- **Internal lib stays `Squad`** (the bundle contains `Squad.json` + `Squad.png`); do not repack/rename. Bundle filename must match the lib: `Squad.nitro`.
- **Single effect slot**: `habbo.Effects.CurrentEffect`; apply/clear via `habbo.Effects.ApplyEffect(id)`. `0` and `-1` both mean "slot free/reset".
- **Assets + `EffectMap.json` are gitignored gamedata** → they do NOT deploy via git; prod needs a manual sync. Emulator code deploys normally (beta first).
- **No em-dashes / special chars in in-game text.** (No new player-facing strings are added by this plan, but keep it in mind.)
- **CHANGELOG.md entry required** (player-facing change).

---

### Task 1: Import the effect bundle and register effect id 248

**Files:**
- Create: `nitro/assets/bundled/effect/Squad.nitro` (copied from the source download)
- Modify: `nitro/assets/gamedata/EffectMap.json` (append one entry)

**Interfaces:**
- Produces: effect id `248` → lib `Squad`, loadable by the Nitro client. Consumed by all later tasks via the constant `Habbo.PassiveEnableEffectId` (defined in Task 2).

- [ ] **Step 1: Confirm the source bundle's internal lib is `Squad`**

Run:
```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
python3 - <<'PY'
import struct
data = open('/Users/rybealey/Downloads/Passive_Enable.nitro','rb').read()
off = 0
count = struct.unpack_from('>H', data, off)[0]; off += 2
names = []
for _ in range(count):
    nl = struct.unpack_from('>H', data, off)[0]; off += 2
    name = data[off:off+nl].decode('latin1'); off += nl
    ln = struct.unpack_from('>I', data, off)[0]; off += 4
    off += ln
    names.append(name)
print('files:', names)
PY
```
Expected: `files: ['Squad.json', 'Squad.png']` (confirms lib `Squad`).

- [ ] **Step 2: Copy the bundle into the effect assets directory**

Run:
```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
cp /Users/rybealey/Downloads/Passive_Enable.nitro nitro/assets/bundled/effect/Squad.nitro
ls -l nitro/assets/bundled/effect/Squad.nitro
```
Expected: file exists, non-zero size.

- [ ] **Step 3: Append effect 248 to EffectMap.json (JSON-safe)**

Run:
```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
python3 - <<'PY'
import json
p = 'nitro/assets/gamedata/EffectMap.json'
d = json.load(open(p))
ids = {e['id'] for e in d['effects']}
assert '248' not in ids, '248 already present'
d['effects'].append({"id":"248","lib":"Squad","type":"fx","revision":75700})
json.dump(d, open(p,'w'), separators=(',',':'))
print('appended; total effects =', len(d['effects']))
PY
```
Expected: `appended; total effects = 248`.

- [ ] **Step 4: Verify the map parses and id 248 resolves**

Run:
```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
python3 -c "import json;d=json.load(open('nitro/assets/gamedata/EffectMap.json'));print([e for e in d['effects'] if e['id']=='248'])"
```
Expected: `[{'id': '248', 'lib': 'Squad', 'type': 'fx', 'revision': 75700}]`

- [ ] **Step 5: Commit (code/config only — the `.nitro` and `EffectMap.json` are gitignored and will not be staged; that is expected)**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add -A
git status   # confirm the gitignored asset/map are NOT staged; nothing to commit here is OK
```
Note: there is intentionally nothing to commit in this task — the asset and map are gitignored gamedata. Record in Task 5 / deploy notes that these two files must be manually synced to beta and prod.

---

### Task 2: Add the effect-id constant and the per-tick arbitration helper

**Files:**
- Modify: `emulator/HabboHotel/Users/Habbo.cs` (add constant near the passive fields, ~line 220)
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs` (add helper; call it after `UpdateUserEffect` at ~line 1322)

**Interfaces:**
- Produces: `public const int Habbo.PassiveEnableEffectId = 248;` — referenced by Tasks 3 and 4.
- Produces: `private void RoomUserManager.UpdatePassiveEffect(RoomUser user)` — the baseline-resume arbiter, called once per user per tick.
- Consumes: effect id 248 registered in Task 1; `habbo.Effects.ApplyEffect(int)`, `habbo.Effects.CurrentEffect`, `habbo.RpPassiveSeconds`, `RoomUser.IsDancing`, `RoomUser.IsBot`.

- [ ] **Step 1: Add the constant in `Habbo.cs`**

In `emulator/HabboHotel/Users/Habbo.cs`, directly above the passive-status fields (the block starting `public int RpPassiveSeconds { get; set; }`, ~line 220), add:

```csharp
// pixelrp: the "passive enable" avatar effect worn while RpPassiveSeconds > 0.
// Maps to nitro/assets/bundled/effect/Squad.nitro via EffectMap.json id 248.
public const int PassiveEnableEffectId = 248;
```

- [ ] **Step 2: Add the `UpdatePassiveEffect` helper in `RoomUserManager.cs`**

In `emulator/HabboHotel/Rooms/RoomUserManager.cs`, directly above the existing `private void UpdateUserEffect(RoomUser user, int x, int y)` method (~line 1951), add:

```csharp
// pixelrp: the passive enable (Squad.nitro, id 248) is a resuming BASELINE
// effect worn while the player is passive. It is asserted only when the
// effect slot is free (0 or -1) and the player is not mid-dance, so a
// dance/ride/tile/item effect temporarily owns the slot and the enable
// comes back on the next tick once that transient effect clears. When the
// player is no longer passive, the enable (and only the enable) is cleared.
private void UpdatePassiveEffect(RoomUser user)
{
    if (user == null || user.IsBot)
        return;
    var habbo = user.GetClient()?.GetHabbo();
    if (habbo?.Effects == null)
        return;

    var cur = habbo.Effects.CurrentEffect;
    if (habbo.RpPassiveSeconds > 0)
    {
        if ((cur == 0 || cur == -1) && !user.IsDancing)
            habbo.Effects.ApplyEffect(Habbo.PassiveEnableEffectId);
    }
    else if (cur == Habbo.PassiveEnableEffectId)
    {
        habbo.Effects.ApplyEffect(0);
    }
}
```

- [ ] **Step 3: Call the helper once per user per tick**

In `emulator/HabboHotel/Rooms/RoomUserManager.cs`, find the per-user tick line (~1322):

```csharp
                    if (!updated) UpdateUserEffect(user, user.X, user.Y);
```

Immediately after it, add:

```csharp
                    UpdatePassiveEffect(user);
```

- [ ] **Step 4: Build the emulator**

Run:
```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
dotnet build "emulator/Plus Emulator.sln" -c Debug
```
Expected: `Build succeeded` with 0 errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add "emulator/HabboHotel/Users/Habbo.cs" "emulator/HabboHotel/Rooms/RoomUserManager.cs"
git commit -m "feat(rp): passive enable baseline effect + per-tick arbitration"
```

---

### Task 3: Immediate apply at the two "enter passive" edges

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Users/RpUseItemEvent.cs` (smoothie, ~line 66)
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs` (room-entry path, ~line 309)

**Interfaces:**
- Consumes: `Habbo.PassiveEnableEffectId` (Task 2), `habbo.Effects.ApplyEffect(int)`.

- [ ] **Step 1: Apply on smoothie consumption**

In `emulator/Communication/Packets/Incoming/Users/RpUseItemEvent.cs`, in the `case "smoothie":` block, find the stats broadcast (~line 66):

```csharp
                if (roomUser != null)
                    habbo.CurrentRoom.SendPacket(new RpStatsComposer(roomUser.VirtualId, habbo.RpHealth, habbo.RpHealthMax, habbo.RpEnergy, habbo.RpEnergyMax, (int)Math.Round(habbo.RpAggression), 1, habbo.Rank >= 5 ? 1 : 0));
```

Immediately after that line (still inside the `if (roomUser != null)` is not required — add as its own statement after the broadcast), add:

```csharp
                // pixelrp: wear the passive enable immediately on activation.
                if (roomUser != null && habbo.Effects != null)
                    habbo.Effects.ApplyEffect(Habbo.PassiveEnableEffectId);
```

- [ ] **Step 2: Apply on room entry when already passive**

In `emulator/HabboHotel/Rooms/RoomUserManager.cs`, find the ambassador forced-effect block (~line 308):

```csharp
        // Staff are no longer given a forced effect (102) on room entry.
        if (session.GetHabbo().IsAmbassador && !session.GetHabbo().DisableForcedEffects && !session.GetHabbo().Permissions.HasRight("mod_tool"))
            session.GetHabbo().Effects.ApplyEffect(178);
```

Immediately after that block, add:

```csharp
        // pixelrp: passive players wear the passive enable on entry so there is
        // no pop on room change; the per-tick helper is the safety net.
        if (session.GetHabbo().RpPassiveSeconds > 0 && session.GetHabbo().Effects != null)
            session.GetHabbo().Effects.ApplyEffect(Habbo.PassiveEnableEffectId);
```

- [ ] **Step 3: Build**

Run:
```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
dotnet build "emulator/Plus Emulator.sln" -c Debug
```
Expected: `Build succeeded`, 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add "emulator/Communication/Packets/Incoming/Users/RpUseItemEvent.cs" "emulator/HabboHotel/Rooms/RoomUserManager.cs"
git commit -m "feat(rp): apply passive enable on smoothie + room entry"
```

---

### Task 4: Immediate clear at the two "exit passive" edges + CHANGELOG

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Users/RpPassiveCancelEvent.cs` (HUD ✕, ~line 27)
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs` (countdown-to-zero, ~line 1264)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `Habbo.PassiveEnableEffectId` (Task 2), `habbo.Effects.CurrentEffect`, `habbo.Effects.ApplyEffect(int)`.

- [ ] **Step 1: Clear on manual cancel (HUD ✕)**

In `emulator/Communication/Packets/Incoming/Users/RpPassiveCancelEvent.cs`, after the stats broadcast (~line 27, the `RpStatsComposer(... , 0, ...)` send), and before `return Task.CompletedTask;`, add:

```csharp
        // pixelrp: drop the passive enable if it (and only it) is showing.
        if (habbo.Effects != null && habbo.Effects.CurrentEffect == Habbo.PassiveEnableEffectId)
            habbo.Effects.ApplyEffect(0);
```

- [ ] **Step 2: Clear on countdown expiry**

In `emulator/HabboHotel/Rooms/RoomUserManager.cs`, find the expiry branch (~line 1260-1264):

```csharp
                            if (habboPas.RpPassiveSeconds == 0)
                            {
                                user.GetClient().SendWhisper("Your passive status has expired.");
                                habboPas.SaveRpStats();
                                _room.SendPacket(new RpStatsComposer(user.VirtualId, habboPas.RpHealth, habboPas.RpHealthMax, habboPas.RpEnergy, habboPas.RpEnergyMax, (int)Math.Round(habboPas.RpAggression), 0, habboPas.Rank >= 5 ? 1 : 0));
                            }
```

Add the clear as the last statement inside that `if` block, after the `_room.SendPacket(...)` line:

```csharp
                                // pixelrp: drop the passive enable if it is the shown effect.
                                if (habboPas.Effects != null && habboPas.Effects.CurrentEffect == Habbo.PassiveEnableEffectId)
                                    habboPas.Effects.ApplyEffect(0);
```

- [ ] **Step 3: Add the CHANGELOG entry**

In `CHANGELOG.md`, add a bullet under the current unreleased/beta section (match the existing entry style at the top of the file):

```markdown
- Passive players now wear a passive enable effect while their passive status is active; it clears automatically when passive ends (expiry or manual cancel).
```

- [ ] **Step 4: Build**

Run:
```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
dotnet build "emulator/Plus Emulator.sln" -c Debug
```
Expected: `Build succeeded`, 0 errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add "emulator/Communication/Packets/Incoming/Users/RpPassiveCancelEvent.cs" "emulator/HabboHotel/Rooms/RoomUserManager.cs" CHANGELOG.md
git commit -m "feat(rp): clear passive enable on cancel + expiry; changelog"
```

---

### Task 5: In-game verification (manual) + deploy sync

**Files:** none (verification + deploy).

This task is Ry's to run in-game (house style: no screenshot-driving the client). It gates the feature as done.

- [ ] **Step 1: Deploy code to beta and sync the gitignored gamedata**

- Push the emulator commits to `beta` (auto-deploys beta.pixelrp.co).
- Manually sync the two gitignored files to the beta stack:
  - `nitro/assets/bundled/effect/Squad.nitro`
  - `nitro/assets/gamedata/EffectMap.json`
- Asset cache gotcha: nginx serves effects with a long `max-age`; force-refresh (or `fetch(url,{cache:'reload'})`) to pick up the new bundle/map, and mint a fresh single-use SSO ticket per reload.

- [ ] **Step 2: Run the verification matrix in-game**

Verify each:
- Drink a Passive Smoothie in a safe zone at full health → passive enable appears immediately.
- Change rooms while passive → enable still on, no lasting pop.
- Walk onto an effect tile (ice/swim) then off → tile effect shows, then the enable resumes within ~1 tick.
- Ride a rideable item → riding effect (77) shows; dismount → enable resumes.
- Dance → dance plays; confirm the enable persists/resumes (client-render behavior to confirm here specifically).
- Stand in a safe zone (countdown frozen) → enable stays on.
- Click the ✕ on the HUD passive tag → enable disappears immediately.
- Let the countdown reach 0 → enable disappears, "passive status has expired" whisper fires.

- [ ] **Step 3: Record the result**

If all pass, the feature is done on beta; merge to main only when Ry says (beta-first house rule). If the enable does not visually survive a dance and that is undesirable, that is a follow-up (client-side), tracked separately — the server logic is correct per this plan.

---

## Self-Review

**Spec coverage:**
- Asset + id 248 + EffectMap → Task 1. ✔
- Constant + baseline-resume arbitration helper + tick hook → Task 2. ✔
- Explicit apply at smoothie + room-entry edges → Task 3. ✔
- Explicit clear at cancel + expiry edges → Task 4. ✔
- Safe-zone stays-on → covered by the helper (passive true in safe zone) + verified in Task 5. ✔
- RCON grant path (tick-only, no explicit apply) → covered by the per-tick helper (Task 2); documented in spec. ✔
- CHANGELOG → Task 4. ✔
- Deploy sync of gitignored gamedata → Task 1 note + Task 5. ✔

**Placeholder scan:** No TBD/TODO; every code step shows exact code and exact insertion point. ✔

**Type consistency:** Constant named `Habbo.PassiveEnableEffectId` (defined Task 2 Step 1) used verbatim in Tasks 2–4. Helper `UpdatePassiveEffect(RoomUser)` defined and called in Task 2. `habbo.Effects.ApplyEffect(int)` / `habbo.Effects.CurrentEffect` match `EffectsComponent`. ✔

**Note on "no unit tests":** deliberate — the emulator has no test project; build + the Task 5 matrix are the gates, consistent with the codebase and house style.
