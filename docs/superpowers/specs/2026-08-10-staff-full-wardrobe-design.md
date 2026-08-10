# Staff Full Wardrobe Access — Design

**Date:** 2026-08-10
**Status:** Approved

## Goal

Users of rank ≥ 4 can use all sellable clothing in the Choose Your Look
window without purchasing it. If a user drops below rank 4, the
unpurchased sellables disappear from their panel and are removed from
their worn figure automatically. Staff should never need to buy clothing.

## Background

Two server-side mechanisms control sellable clothing:

1. **Panel visibility.** At login, `SsoTicketEvent` sends
   `FigureSetIdsComposer` with the part IDs the user owns (from
   `user_clothing`). The Nitro client only unlocks sellable figure sets
   whose IDs appear in this packet. Entirely server-driven.
2. **Save validation.** `FigureDataManager.ProcessFigure` strips any
   figure part that exists in `catalog_clothing` but is not in the
   `clothingParts` collection passed to it. When `clothingParts` is
   `null`, this ownership check is skipped entirely (existing behavior).

## Design

### Gate

New property on `Habbo` (emulator/HabboHotel/Users/Habbo.cs), next to
`IsStaff`:

```csharp
public bool HasFullWardrobe => Rank >= 4;
```

Single definition of the threshold; no magic numbers at call sites.

### Panel unlock (FigureSetIdsComposer)

When the user has `HasFullWardrobe`, send the union of:

- their real owned parts (`Clothing.GetClothingParts`), and
- a synthetic `ClothingParts` entry for every part ID in
  `ClothingManager.GetClothingAllParts` (each entry carries the
  `clothing_name` from `catalog_clothing`),

deduplicated by part ID. Build the union in one small shared helper used
by both send sites:

- `SsoTicketEvent` (login) — requires injecting the clothing manager
  (`ICatalogManager` or `IClothingManager`) into its constructor; DI is
  already wired for this class.
- `UseSellableClothingEvent` (clothing-furni redeem resend) — so
  redeeming a clothing furni doesn't collapse a staff member's list.

### Save validation bypass

At the four `ProcessFigure` call sites, pass `null` for `clothingParts`
when the user has `HasFullWardrobe`:

- `Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs` (login sanitize)
- `Communication/Packets/Incoming/Users/UpdateFigureDataEvent.cs` (look save)
- `Communication/Packets/Incoming/Avatar/SaveWardrobeOutfitEvent.cs` (wardrobe save)
- `HabboHotel/Rooms/Chat/Commands/User/Fun/FacelessCommand.cs`

No changes to `ProcessFigure` itself.

### Demotion (automatic revocation)

Nothing is granted or persisted, so nothing needs revoking. On the next
login below rank 4:

- `FigureSetIdsComposer` contains only genuinely purchased parts, so the
  panel no longer shows unpurchased sellables.
- The login-time `ProcessFigure` call receives the real owned list again
  and swaps any still-worn unpurchased sellable parts out of the figure.

A user demoted mid-session keeps access until relog, consistent with how
rank changes behave elsewhere in the emulator.

### Out of scope / untouched

- No client changes, no DB schema changes, no cleanup jobs.
- Clothing a rank ≥ 4 user legitimately purchased earlier is unaffected:
  those are real `user_clothing` rows and survive demotion.

## Testing

Manual verification on local dev with the ClaudeTest account:

1. Set rank ≥ 4, relog: all sellable sets appear in Choose Your Look.
2. Save a look containing an unpurchased sellable; relog: look persists.
3. Drop rank to 1, relog: sellables gone from the panel and the worn
   figure has been sanitized (unpurchased parts replaced).
4. Regression: a rank-1 user with a purchased item still sees and keeps
   that item.

CHANGELOG.md entry required (player-facing change).
