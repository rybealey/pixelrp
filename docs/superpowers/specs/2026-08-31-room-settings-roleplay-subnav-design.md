# Room Settings › Roleplay sidebar — design

2026-08-31. Client-only change (submodule `client/`, branch `pixelrp`). No
emulator work, no new wire ids, no data-flow changes.

## Goal

Reorganize the Room Settings window's Roleplay tab to match the Settings
window's sub-navigation pattern: a slim left rail of page links grouped
under uppercase eyebrow headers, with the selected page's content on the
right. First eyebrow is **General**; its first (and initially only) link is
**Zoning**, which hosts the existing Zone Type control. The rail gives
future roleplay room settings an obvious home.

## 1. Shared subnav pattern

The sidebar styles currently live in
`client/src/components/rp-settings/RpSettingsView.scss`, scoped under
`.nitro-card.rp-settings-window`, so they are unusable from the Room
Settings window. They move verbatim into a new shared partial:

- **New file:** `client/src/assets/styles/_subnav.scss`, imported from
  `client/src/assets/styles/index.scss` after `chrome` (the active pill
  uses `--prp-chrome-95`; the item radius uses Bootstrap's
  `$border-radius`, which is in scope by import order).
- **Renames** (generic, unscoped classes):

  | Old (Settings-scoped)       | New (shared)         |
  |-----------------------------|----------------------|
  | `rp-settings-subnav-layout` | `prp-subnav-layout`  |
  | `rp-settings-subnav`        | `prp-subnav`         |
  | `rp-settings-subnav-eyebrow`| `prp-subnav-eyebrow` |
  | `rp-settings-subnav-item`   | `prp-subnav-item`    |
  | `rp-settings-subpage`       | `prp-subnav-page`    |

- The rules move unchanged: 124px fixed rail (sized to the widest label
  across the Settings tabs so every rail lines up), right border, eyebrow
  typography, hover/active states, and the page column's
  `flex: 1 / min-width: 0 / overflow-y: auto` scroll behavior.
- `RpSettingsView.tsx` swaps to the new class names everywhere it uses the
  old ones. `RpSettingsView.scss` drops the moved blocks. Zero visual
  change in the Settings window.
- Classes not part of the pattern (`rp-settings-section`,
  `rp-settings-placeholder`, swatches, Discord page, skeletons) stay where
  they are.

## 2. Roleplay tab restructure

`client/src/components/navigator/views/room-settings/NavigatorRoomSettingsRoleplayTabView.tsx`:

- Local `page` state, default `'Zoning'`, with a `GENERAL_PAGES: string[]`
  list mirroring the Settings window's per-tab page lists.
- Renders `prp-subnav-layout` → rail (`prp-subnav-eyebrow` "General",
  `prp-subnav-item` per page) + `prp-subnav-page` content column.
- The Zoning page keeps the existing content unchanged — bold "Zone Type",
  the safe-zone description, and the Safe/Unsafe `select` — stacked
  vertically, because the ~250px content column is too narrow for the
  Settings window's label-left/control-right row style.
- Zone state stays hoisted in `NavigatorRoomSettingsView` (`isSafeZone` /
  `setIsSafeZone`), exactly as today: the `RpRoomZoneEvent` packet arrives
  before the tab mounts, so the parent must hold it. Saving still sends
  `RpRoomZoneSaveComposer` on change.

## 3. Sizing

`client/src/components/navigator/NavigatorView.scss`, inside the existing
`.nitro-room-settings` block:

```scss
.prp-subnav-layout {
    min-height: 260px;
}
```

Window width stays 400px; other tabs keep their auto height. The rail
squeezes the content column to roughly 250px, which fits the zone control
and future stacked rows.

## 4. Ship path

1. Commit + push in the `client` submodule (branch `pixelrp`).
2. Bump the submodule pointer on the parent `beta` branch (auto-deploys
   beta.pixelrp.co).
3. Player-facing CHANGELOG bullet (the tab is visible to room owners).
4. Verification: `yarn build` passes; manual in-game check on beta (no
   client test infra).

## Error handling / testing

No new failure modes: no new packets, no new async paths. The only state
added is a local string. Existing behavior (zone save on dropdown change)
is untouched. Verification is the build plus the in-game check above.

## Rejected alternatives

- **Whole-window sidebar** (rail spanning all five tabs): stock tabs are
  single-page forms that gain nothing from a rail; the ask is scoped to
  the Roleplay tab.
- **Scope-extend or copy the CSS** instead of promoting it: either leaks
  Settings naming into the navigator or forks the styles to drift; the
  shared partial matches how the chrome tab strip already became a shared
  mixin.
- **Widening the window** to fit label-left/control-right rows: changes
  how all stock tabs look for one tab's benefit.
