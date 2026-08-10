# Staff Full Wardrobe Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users of rank ≥ 4 see and can wear every sellable clothing set in the Choose Your Look window without purchasing; demotion below rank 4 revokes this automatically at next login.

**Architecture:** Two server-side mechanisms control sellable clothing: the `FigureSetIdsComposer` packet (sent at login) tells the Nitro client which sellable figure sets to unlock, and `FigureDataManager.ProcessFigure` strips unowned purchasable parts on every figure save (skipped entirely when its `clothingParts` argument is `null`). We add a `HasFullWardrobe` gate on `Habbo`, send the union of owned + all catalog parts at the two packet send sites, and pass `null` to `ProcessFigure` at its four call sites for gated users. Nothing is persisted, so demotion needs no cleanup.

**Tech Stack:** C# (.NET, PlusEMU emulator — the `emulator/` git submodule, branch `pixelrp`). Built via Docker: `docker compose build emulator` from the repo root.

**Spec:** `docs/superpowers/specs/2026-08-10-staff-full-wardrobe-design.md`

## Global Constraints

- Threshold is **rank ≥ 4**, defined once as `Habbo.HasFullWardrobe`. No magic `4` anywhere else.
- No client changes, no DB schema changes, no new DB rows granted to staff.
- `FigureDataManager.ProcessFigure` itself is NOT modified.
- The emulator has **no test project** — there is no `*Tests.csproj` anywhere in the solution. Verification is (a) the Docker image build, which compiles the solution and fails on any compile error, and (b) the live smoke test in Task 4. Do not create a test project.
- Emulator commits happen **inside the `emulator/` submodule** on branch `pixelrp` (conventional-commit style, e.g. `feat(clothing): …`). The parent repo commit (submodule pointer bump + CHANGELOG) is Task 5 and must not happen before the emulator work is committed.
- Every player-facing change needs a `CHANGELOG.md` entry in the parent repo (house rule).

---

### Task 1: `HasFullWardrobe` gate + union helper

**Files:**
- Modify: `emulator/HabboHotel/Users/Habbo.cs:68` (add property below `IsStaff`)
- Create: `emulator/HabboHotel/Users/Clothing/FullWardrobeUtility.cs`

**Interfaces:**
- Consumes: `Habbo.Rank` (int), `Habbo.Clothing.GetClothingParts` (`ICollection<ClothingParts>`), `IClothingManager.GetClothingAllParts` (`ICollection<ClothingItem>`, each with `ClothingName` (string) and `PartIds` (`List<int>`)), `ClothingParts(int id, int partId, string part)` constructor.
- Produces: `Habbo.HasFullWardrobe` (bool property) and `static ICollection<ClothingParts> FullWardrobeUtility.GetVisibleClothingParts(Habbo habbo, IClothingManager clothingManager)` — Tasks 2 and 3 call exactly these.

- [ ] **Step 1: Add the gate property to Habbo**

In `emulator/HabboHotel/Users/Habbo.cs`, directly below the existing `IsStaff` property (line 68), add:

```csharp
    // Full-wardrobe cutoff: rank 4+ can wear any sellable clothing set
    // without owning a user_clothing row (see FullWardrobeUtility).
    public bool HasFullWardrobe => Rank >= 4;
```

- [ ] **Step 2: Create the union helper**

Create `emulator/HabboHotel/Users/Clothing/FullWardrobeUtility.cs` with exactly:

```csharp
using Plus.HabboHotel.Catalog.Clothing;
using Plus.HabboHotel.Users.Clothing.Parts;

namespace Plus.HabboHotel.Users.Clothing;

public static class FullWardrobeUtility
{
    /// <summary>
    /// The clothing parts to advertise to the client via FigureSetIdsComposer.
    /// Full-wardrobe users get every purchasable part unioned with their own;
    /// everyone else gets only what they own.
    /// </summary>
    public static ICollection<ClothingParts> GetVisibleClothingParts(Habbo habbo, IClothingManager clothingManager)
    {
        if (!habbo.HasFullWardrobe)
            return habbo.Clothing.GetClothingParts;
        var parts = new Dictionary<int, ClothingParts>();
        foreach (var owned in habbo.Clothing.GetClothingParts)
            parts.TryAdd(owned.PartId, owned);
        foreach (var clothing in clothingManager.GetClothingAllParts)
            foreach (var partId in clothing.PartIds)
                parts.TryAdd(partId, new(0, partId, clothing.ClothingName));
        return parts.Values;
    }
}
```

Notes for the implementer: the synthetic entries use DB row id `0` because they are never written back to `user_clothing`; `FigureSetIdsComposer` only reads `PartId` and `Part`. The dictionary dedupes owned vs. catalog parts by `PartId`, owned entries winning.

- [ ] **Step 3: Verify it compiles**

From the repo root (`/Users/rybealey/Documents/Personal/pixelrp/plus`):

```bash
docker compose build emulator
```

Expected: build succeeds (the Dockerfile runs the .NET build; any compile error fails the image build).

- [ ] **Step 4: Commit (inside the submodule)**

```bash
cd emulator
git add "HabboHotel/Users/Habbo.cs" "HabboHotel/Users/Clothing/FullWardrobeUtility.cs"
git commit -m "feat(clothing): add full-wardrobe gate (rank >= 4) and part-union helper"
```

---

### Task 2: Send the union at both `FigureSetIdsComposer` send sites

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs` (constructor DI + line 86)
- Modify: `emulator/Communication/Packets/Incoming/Rooms/Furni/UseSellableClothingEvent.cs:63`

**Interfaces:**
- Consumes: `FullWardrobeUtility.GetVisibleClothingParts(Habbo, IClothingManager)` from Task 1; `IClothingManager` (already DI-registered — `UseSellableClothingEvent` proves it resolves).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Inject `IClothingManager` into `SsoTicketEvent`**

In `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs`:

Add to the using block at the top (it is not currently imported):

```csharp
using Plus.HabboHotel.Catalog.Clothing;
using Plus.HabboHotel.Users.Clothing;
```

Add a field alongside the existing ones (after `private readonly IRewardManager _rewardManager;`):

```csharp
    private readonly IClothingManager _clothingManager;
```

Add `IClothingManager clothingManager,` as a constructor parameter (before the `ILogger<SsoTicketEvent> logger` parameter) and assign it in the body:

```csharp
        _clothingManager = clothingManager;
```

- [ ] **Step 2: Replace the login send (line 86)**

Change:

```csharp
            session.Send(new FigureSetIdsComposer(session.GetHabbo().Clothing.GetClothingParts));
```

to:

```csharp
            session.Send(new FigureSetIdsComposer(FullWardrobeUtility.GetVisibleClothingParts(session.GetHabbo(), _clothingManager)));
```

- [ ] **Step 3: Replace the redeem-resend (UseSellableClothingEvent.cs:63)**

In `emulator/Communication/Packets/Incoming/Rooms/Furni/UseSellableClothingEvent.cs`, add to the usings:

```csharp
using Plus.HabboHotel.Users.Clothing;
```

then change line 63 from:

```csharp
        session.Send(new FigureSetIdsComposer(session.GetHabbo().Clothing.GetClothingParts));
```

to:

```csharp
        session.Send(new FigureSetIdsComposer(FullWardrobeUtility.GetVisibleClothingParts(session.GetHabbo(), _clothingManager)));
```

(`_clothingManager` already exists in this class.)

- [ ] **Step 4: Verify it compiles**

```bash
docker compose build emulator
```

Expected: build succeeds.

- [ ] **Step 5: Commit (inside the submodule)**

```bash
cd emulator
git add "Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs" "Communication/Packets/Incoming/Rooms/Furni/UseSellableClothingEvent.cs"
git commit -m "feat(clothing): advertise all sellable figure sets to rank 4+ users"
```

---

### Task 3: Bypass ownership stripping in `ProcessFigure` for gated users

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs:117`
- Modify: `emulator/Communication/Packets/Incoming/Users/UpdateFigureDataEvent.cs:30`
- Modify: `emulator/Communication/Packets/Incoming/Avatar/SaveWardrobeOutfitEvent.cs:25`
- Modify: `emulator/HabboHotel/Rooms/Chat/Commands/User/Fun/FacelessCommand.cs:45`

**Interfaces:**
- Consumes: `Habbo.HasFullWardrobe` from Task 1. `ProcessFigure(string figure, string gender, ICollection<ClothingParts> clothingParts, bool hasHabboClub)` already skips its ownership-strip block when `clothingParts` is `null` (see `FigureDataManager.cs:198` — `if (clothingParts != null)`); we rely on that existing behavior and do not touch the method.
- Produces: nothing new for later tasks.

The pattern at all four sites is identical: replace the argument `session.GetHabbo().Clothing.GetClothingParts` with `session.GetHabbo().HasFullWardrobe ? null : session.GetHabbo().Clothing.GetClothingParts`. Exact edits:

- [ ] **Step 1: SSOTicketEvent.cs:117 (login-time figure sanitize)**

Change:

```csharp
            session.GetHabbo().Look = _figureManager.ProcessFigure(session.GetHabbo().Look, session.GetHabbo().Gender, session.GetHabbo().Clothing.GetClothingParts, true);
```

to:

```csharp
            session.GetHabbo().Look = _figureManager.ProcessFigure(session.GetHabbo().Look, session.GetHabbo().Gender, session.GetHabbo().HasFullWardrobe ? null : session.GetHabbo().Clothing.GetClothingParts, true);
```

This line is also what sanitizes a demoted user's worn figure at their next login — with `HasFullWardrobe` now false, the real owned list is passed again and unpurchased sellable parts get swapped out.

- [ ] **Step 2: UpdateFigureDataEvent.cs:30 (look save)**

Change:

```csharp
        var look = _figureManager.ProcessFigure(packet.ReadString(), gender, session.GetHabbo().Clothing.GetClothingParts, true);
```

to:

```csharp
        var look = _figureManager.ProcessFigure(packet.ReadString(), gender, session.GetHabbo().HasFullWardrobe ? null : session.GetHabbo().Clothing.GetClothingParts, true);
```

- [ ] **Step 3: SaveWardrobeOutfitEvent.cs:25 (wardrobe slot save)**

Change:

```csharp
        look = _figureDataManager.ProcessFigure(look, gender, session.GetHabbo().Clothing.GetClothingParts, true);
```

to:

```csharp
        look = _figureDataManager.ProcessFigure(look, gender, session.GetHabbo().HasFullWardrobe ? null : session.GetHabbo().Clothing.GetClothingParts, true);
```

- [ ] **Step 4: FacelessCommand.cs:45**

Change:

```csharp
        session.GetHabbo().Look = _figureDataManager.ProcessFigure(session.GetHabbo().Look, session.GetHabbo().Gender, session.GetHabbo().Clothing.GetClothingParts, true);
```

to:

```csharp
        session.GetHabbo().Look = _figureDataManager.ProcessFigure(session.GetHabbo().Look, session.GetHabbo().Gender, session.GetHabbo().HasFullWardrobe ? null : session.GetHabbo().Clothing.GetClothingParts, true);
```

- [ ] **Step 5: Verify it compiles**

```bash
docker compose build emulator
```

Expected: build succeeds.

- [ ] **Step 6: Commit (inside the submodule)**

```bash
cd emulator
git add "Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs" "Communication/Packets/Incoming/Users/UpdateFigureDataEvent.cs" "Communication/Packets/Incoming/Avatar/SaveWardrobeOutfitEvent.cs" "HabboHotel/Rooms/Chat/Commands/User/Fun/FacelessCommand.cs"
git commit -m "feat(clothing): skip figure ownership stripping for rank 4+ users"
```

---

### Task 4: Live verification on the local dev stack

No code changes. Verifies the spec's four test scenarios against the running stack. The local hotel is at `http://localhost:8080` (CMS) with the Nitro client; log in as **ClaudeTest** via the SSO-ticket flow (set an `auth_ticket` in the DB, then open the client with `?sso=<ticket>` — same procedure used for all prior live testing on this project). DB is the `db` compose service, database name `pixelrp`.

- [ ] **Step 1: Rebuild and restart the emulator with the new code**

```bash
docker compose up -d --build emulator
```

Wait for the emulator log to show it accepting connections: `docker compose logs -f emulator` (Ctrl-C once ready).

- [ ] **Step 2: Promote ClaudeTest to rank 4**

```bash
docker compose exec db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -e "UPDATE users SET \`rank\` = 4 WHERE username = \"ClaudeTest\";"'
```

- [ ] **Step 3: Scenario 1 — panel shows all sellables**

Log in as ClaudeTest, open Choose Your Look. Expected: sellable clothing sets (e.g. the chrome chain chest accessory and other `catalog_clothing` entries) are selectable, not locked, despite `user_clothing` having no rows for them (`SELECT * FROM user_clothing WHERE user_id = (SELECT id FROM users WHERE username = 'ClaudeTest');` to confirm ownership is empty).

- [ ] **Step 4: Scenario 2 — save persists**

Put on an unpurchased sellable set, save the look, then relog (fresh SSO ticket). Expected: the figure still contains the sellable part after relog — check visually and via `SELECT look FROM users WHERE username = 'ClaudeTest';` (the part id must still be present in the figure string).

- [ ] **Step 5: Scenario 3 — demotion revokes**

```bash
docker compose exec db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -e "UPDATE users SET \`rank\` = 1 WHERE username = \"ClaudeTest\";"'
```

Relog as ClaudeTest. Expected: (a) the sellable sets are locked/absent again in Choose Your Look, and (b) the worn figure was sanitized at login — the unpurchased part is gone from `SELECT look FROM users WHERE username = 'ClaudeTest';`.

- [ ] **Step 6: Scenario 4 — regression: legitimately purchased clothing survives at rank 1**

While still rank 1, redeem or grant one clothing item the normal way (insert a real ownership row for a set that exists in `catalog_clothing`, e.g. via the clothing furni redeem flow, or `INSERT INTO user_clothing (user_id, part_id, part) VALUES (...)` matching one `catalog_clothing` part id), relog. Expected: that set is unlocked in the panel and wearable; all other sellables remain locked.

- [ ] **Step 7: Restore ClaudeTest to its usual rank** (whatever it was before testing — check first with `SELECT \`rank\` FROM users ...` in Step 2 and note it down).

---

### Task 5: Parent repo — submodule bump + CHANGELOG

Only after Tasks 1–4 are complete and verified.

**Files:**
- Modify: `CHANGELOG.md` (parent repo)
- Modify: `emulator` submodule pointer (parent repo)

- [ ] **Step 1: Add the CHANGELOG entry**

Follow the existing format in `CHANGELOG.md` (read the top of the file first and match its date/section style). Entry text:

```markdown
- Staff (rank 4+) can now use all sellable clothing in Choose Your Look without purchasing it. Access is removed automatically if demoted below rank 4.
```

- [ ] **Step 2: Commit the bump in the parent repo**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add emulator CHANGELOG.md
git commit -m "feat: bump emulator - staff (rank 4+) full wardrobe access

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(Do not push or deploy — deploys go through the GitHub Actions workflow and are a separate, user-initiated decision.)
