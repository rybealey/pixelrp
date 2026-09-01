# Room Settings › Roleplay Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the Room Settings window's Roleplay tab into the Settings window's sub-navigation pattern (left rail, eyebrow headers), promoting the sidebar styles to shared `prp-subnav-*` classes; first eyebrow "General", first link "Zoning".

**Architecture:** Client-only (submodule `client/`, branch `pixelrp`). The subnav SCSS moves verbatim from the Settings-scoped block in `RpSettingsView.scss` into a new shared partial `_subnav.scss` with generic class names; `RpSettingsView.tsx` swaps to the new names (zero visual change); the Roleplay tab view re-renders its existing zoning control inside the shared layout. Spec: `docs/superpowers/specs/2026-08-31-room-settings-roleplay-subnav-design.md`.

**Tech Stack:** React 18 + TypeScript (nitro-react fork), Sass (classic `@import`), Vite, yarn Berry.

## Global Constraints

- All client work happens inside the `client/` **git submodule** (repo `rybealey/nitro-react`, branch `pixelrp`). Commits in the parent repo do NOT capture client changes.
- Code style: 4-space indent, single quotes, spaces inside JSX braces (`{ page }`), Allman-ish brace-on-next-line for functions — match the surrounding files exactly.
- No TDD cycle: the client has **no test infrastructure**. Verification per task = `yarn build` from `client/` must succeed (plus lint of touched files).
- The CHANGELOG renders in-game (deployment screen): **no em-dashes** — use ` - ` (spaced hyphen) like the existing entries.
- Do not touch `nitro-renderer` or any packet/wire code — this feature adds none.
- Pushing the parent `beta` branch auto-deploys beta.pixelrp.co — Task 3 does this deliberately, and only Task 3 pushes anything.

---

### Task 1: Promote the subnav styles to shared `prp-subnav-*` classes

**Files:**
- Create: `client/src/assets/styles/_subnav.scss`
- Modify: `client/src/assets/styles/index.scss:1-7` (import list)
- Modify: `client/src/components/rp-settings/RpSettingsView.scss:5-62` and `:130-137` (delete moved blocks)
- Modify: `client/src/components/rp-settings/RpSettingsView.tsx:254-344` (class renames)

**Interfaces:**
- Consumes: `--prp-chrome-95` CSS var (defined in `_chrome.scss`), Bootstrap SCSS vars `$border-radius`, `$white` (in scope because `index.scss` imports bootstrap first).
- Produces: global classes `prp-subnav-layout`, `prp-subnav`, `prp-subnav-eyebrow`, `prp-subnav-item`, `prp-subnav-page` — Task 2 consumes these from the navigator.

- [ ] **Step 1: Create the shared partial**

Write `client/src/assets/styles/_subnav.scss` with exactly this content (the rules are moved verbatim from `RpSettingsView.scss`; only the class names and the two comments referencing "consumers" change):

```scss
// Shared sub-navigation pattern: a slim left rail of page links, grouped
// under uppercase eyebrow headers, beside the selected page's content.
// Used by the Settings window and Room Settings > Roleplay. The active
// link is a chrome-colored pill - it echoes the tab strip and follows the
// player's UI color scheme.
.prp-subnav-layout {
    display: flex;
    height: 100%;
    gap: 12px;
}

.prp-subnav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    // Fixed rail so every consumer's sidebar lines up; sized to the widest
    // page label across the Settings tabs ("Personalization", 88.7px at
    // 12px bold Ubuntu) + item padding + rail padding/border, with headroom.
    width: 124px;
    flex-shrink: 0;
    padding-right: 10px;
    border-right: 1px solid rgba(0, 0, 0, 0.08);
}

// Eyebrow header sectioning groups of subnav links (e.g. "Interface"
// above Windows / Components on the Settings window's System tab).
.prp-subnav-eyebrow {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(0, 0, 0, 0.4);
    padding: 4px 10px 2px;

    &:not(:first-child) {
        margin-top: 10px;
    }
}

.prp-subnav-item {
    padding: 5px 10px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    border-radius: $border-radius;
    font-size: 12px;
    font-weight: 700;
    color: rgba(0, 0, 0, 0.45);
    cursor: pointer;
    transition: background 0.1s ease, color 0.1s ease;

    &:hover {
        color: rgba(0, 0, 0, 0.8);
    }

    &.is-active {
        background: var(--prp-chrome-95);
        color: $white;
    }
}

.prp-subnav-page {
    flex: 1;
    min-width: 0;
    // never scroll sideways; scroll vertically only if a page runs tall
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
}
```

- [ ] **Step 2: Import the partial**

In `client/src/assets/styles/index.scss`, add `@import './subnav';` on the line after `@import './chrome';` (it must come after bootstrap for `$border-radius`/`$white` and reads naturally next to chrome, whose var it uses):

```scss
@import './fonts';
@import './bootstrap/bootstrap';
@import './chrome';
@import './subnav';
@import './scrollbars';
@import './slider';
@import './icons';
@import './utils';
```

- [ ] **Step 3: Delete the moved blocks from `RpSettingsView.scss`**

Inside the `.nitro-card.rp-settings-window { ... }` block, delete these five rule blocks **and their leading comments** (currently lines 5–62 and 130–137):
- the `// Sub-navigation layout ...` comment + `.rp-settings-subnav-layout { ... }`
- `.rp-settings-subnav { ... }` (including the `// Fixed rail ...` comment inside it)
- the `// Eyebrow header ...` comment + `.rp-settings-subnav-eyebrow { ... }`
- `.rp-settings-subnav-item { ... }`
- `.rp-settings-subpage { ... }`

Everything else in the file (`rp-settings-discord*`, `rp-settings-skeleton*`, `rp-settings-section*`, swatches, placeholder, stack-section, width/height on the window) stays.

- [ ] **Step 4: Rename the classes in `RpSettingsView.tsx`**

Replace every occurrence (16 total, lines 254–344), longest names first so substring names don't mangle them:

| Old | New | Occurrences |
|---|---|---|
| `rp-settings-subnav-layout` | `prp-subnav-layout` | 3 |
| `rp-settings-subnav-eyebrow` | `prp-subnav-eyebrow` | 5 |
| `rp-settings-subnav-item` | `prp-subnav-item` | 4 |
| `rp-settings-subnav` | `prp-subnav` | 3 (the bare rail divs) |
| `rp-settings-subpage` | `prp-subnav-page` | 3 (incl. one combined `"rp-settings-placeholder rp-settings-subpage"` → `"rp-settings-placeholder prp-subnav-page"`) |

From `client/`:

```bash
perl -pi -e 's/rp-settings-subnav-layout/prp-subnav-layout/g; s/rp-settings-subnav-eyebrow/prp-subnav-eyebrow/g; s/rp-settings-subnav-item/prp-subnav-item/g; s/rp-settings-subnav/prp-subnav/g; s/rp-settings-subpage/prp-subnav-page/g' src/components/rp-settings/RpSettingsView.tsx
```

Then verify no old names remain anywhere:

```bash
grep -rn "rp-settings-subnav\|rp-settings-subpage" src/ && echo "LEFTOVERS" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 5: Build to verify**

Run from `client/`: `yarn build`
Expected: completes without errors (Sass would fail the build on an undefined `$border-radius`/`$white` if the import order were wrong).

- [ ] **Step 6: Commit (inside the client submodule)**

```bash
cd client
git add src/assets/styles/_subnav.scss src/assets/styles/index.scss src/components/rp-settings/RpSettingsView.scss src/components/rp-settings/RpSettingsView.tsx
git commit -m "refactor(styles): promote settings subnav to shared prp-subnav classes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Rebuild the Roleplay tab on the shared subnav

**Files:**
- Modify: `client/src/components/navigator/views/room-settings/NavigatorRoomSettingsRoleplayTabView.tsx` (full rewrite, 39 lines → ~55)
- Modify: `client/src/components/navigator/NavigatorView.scss:58-75` (inside `.nitro-room-settings`)

**Interfaces:**
- Consumes: `prp-subnav-*` classes from Task 1; existing props `roomData`, `isSafeZone`, `setIsSafeZone` (unchanged — the parent `NavigatorRoomSettingsView` keeps holding zone state); `RpRoomZoneSaveComposer` (existing packet, unchanged).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Rewrite the tab view**

Replace the body of `NavigatorRoomSettingsRoleplayTabView.tsx` with:

```tsx
import { RpRoomZoneSaveComposer } from '@nitrots/nitro-renderer';
import { FC, useState } from 'react';
import { IRoomData, SendMessageComposer } from '../../../../api';
import { Column, Text } from '../../../../common';

// PixelRP roleplay room settings, laid out like the Settings window: a
// left rail of page links under eyebrow headers (shared prp-subnav-*
// classes) so future roleplay options have an obvious home. Zone Type:
// safe zones freeze the passive countdown for everyone in the room
// (enforced server-side); the value arrives via RpRoomZoneEvent alongside
// the stock settings data and is held by the parent so it survives tab
// switches.
const GENERAL_PAGES: string[] = [ 'Zoning' ];

interface NavigatorRoomSettingsRoleplayTabViewProps
{
    roomData: IRoomData;
    isSafeZone: boolean;
    setIsSafeZone: (value: boolean) => void;
}

export const NavigatorRoomSettingsRoleplayTabView: FC<NavigatorRoomSettingsRoleplayTabViewProps> = props =>
{
    const { roomData = null, isSafeZone = false, setIsSafeZone = null } = props;
    const [ generalPage, setGeneralPage ] = useState<string>(GENERAL_PAGES[0]);

    const saveZone = (value: string) =>
    {
        const safe = (value === 'safe');

        setIsSafeZone(safe);
        SendMessageComposer(new RpRoomZoneSaveComposer(safe));
    }

    return (
        <div className="prp-subnav-layout">
            <div className="prp-subnav">
                <div className="prp-subnav-eyebrow">General</div>
                { GENERAL_PAGES.map(page => (
                    <div key={ page }
                        className={ `prp-subnav-item ${ (generalPage === page) ? 'is-active' : '' }` }
                        onClick={ () => setGeneralPage(page) }>
                        { page }
                    </div>
                )) }
            </div>
            <Column gap={ 1 } className="prp-subnav-page">
                { (generalPage === 'Zoning') &&
                    <>
                        <Text bold>Zone Type</Text>
                        <Text>Safe zones pause every visitor&apos;s passive countdown - time only ticks in unsafe rooms.</Text>
                        <select className="form-select form-select-sm" value={ isSafeZone ? 'safe' : 'unsafe' } onChange={ event => saveZone(event.target.value) }>
                            <option value="safe">Safe</option>
                            <option value="unsafe">Unsafe</option>
                        </select>
                    </> }
            </Column>
        </div>
    );
}
```

(The zoning content — label, description, select, `saveZone` — is byte-identical to the current file; only the wrapper changed.)

- [ ] **Step 2: Give the layout presence in the room-settings window**

In `client/src/components/navigator/NavigatorView.scss`, inside the existing `.nitro-room-settings { ... }` block (after the `&.theme-primary...` tab-strip rule, before `.list-container`), add:

```scss
    // Roleplay tab rail (shared subnav): keep sidebar-height presence even
    // while the tab has a single link.
    .prp-subnav-layout {
        min-height: 260px;
    }
```

- [ ] **Step 3: Build to verify**

Run from `client/`: `yarn build`
Expected: success.

- [ ] **Step 4: Visual sanity check (optional but cheap)**

Start the dev client (`.claude/launch.json` → `client`, port 5173) against the local stack, open a room you own → room settings → Roleplay tab. Expect: rail on the left with GENERAL eyebrow + active "Zoning" pill in the player's chrome color, zone dropdown on the right, window ~260px tall content area. Settings window (System/Roleplay/Social tabs) must look unchanged. Skip if no local stack is running — the beta check in Task 3 covers it.

- [ ] **Step 5: Commit (inside the client submodule)**

```bash
cd client
git add src/components/navigator/views/room-settings/NavigatorRoomSettingsRoleplayTabView.tsx src/components/navigator/NavigatorView.scss
git commit -m "feat(room-settings): roleplay tab subnav - General > Zoning

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Ship to beta (submodule push, pointer bump, changelog)

**Files:**
- Modify: `CHANGELOG.md:16` (new release heading directly under the maintainer comment block)
- Modify: parent repo gitlink `client` (submodule pointer bump)

**Interfaces:**
- Consumes: the two commits from Tasks 1–2 on the client submodule's `pixelrp` branch.
- Produces: a deployed beta for the user's in-game verification.

- [ ] **Step 1: Push the client submodule**

```bash
cd client
git push origin HEAD:pixelrp
```

Expected: pushes both commits to `rybealey/nitro-react` branch `pixelrp`. (Without this, the parent pointer bump would reference unreachable commits and the beta deploy's submodule checkout would fail.)

- [ ] **Step 2: Add the changelog entry**

In `CHANGELOG.md`, insert directly above the current top release (`## 2026-08-31 — Clock in, get paid`):

```markdown
## 2026-08-31 — Room settings, roleplay edition

### Changed

- **The Roleplay tab in Room settings got the Settings treatment.** Its
  options now sit in a sidebar on the left - Zoning holds the safe/unsafe
  zone picker - so new roleplay room options have an obvious home as they
  arrive.

```

(Player-facing wording, spaced hyphens only — this text renders in-game on the deployment screen.)

- [ ] **Step 3: Commit the pointer bump + changelog in the parent repo, on `beta`**

```bash
git add client CHANGELOG.md
git commit -m "feat(room-settings): roleplay tab subnav - General > Zoning (bump client)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Verify before committing: `git diff --cached --submodule` shows the client pointer moving from `19ac8b21` to the new head.

- [ ] **Step 4: Push beta (this deploys)**

```bash
git push origin beta
```

Expected: `deploy-beta.yml` builds the client and deploys beta.pixelrp.co; `changelog-discord.yml` posts the new bullet to #planned; `commits-discord.yml` posts the commit to #commits.

- [ ] **Step 5: Watch the deploy**

```bash
gh run watch $(gh run list --workflow deploy-beta.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

Expected: green. The browser bundle hash changing (a new `index-*.js` under `/nitro-assets/client/assets/`) is the tell that the client half actually shipped.

- [ ] **Step 6: Hand off for in-game verification**

Tell the user it's live on beta and what to check: Room settings → Roleplay tab shows the GENERAL/Zoning rail; flipping Safe/Unsafe still saves (whisper/behavior unchanged); the Settings window's three tabs look identical to before. (Per project preference, in-game verification is the user's, not a screenshot-driven client session.)

---

## Self-Review

- **Spec coverage:** §1 shared partial + renames → Task 1; §2 tab restructure → Task 2 Step 1; §3 min-height → Task 2 Step 2; §4 ship path (submodule push, pointer bump, changelog, build + in-game verification) → Task 3. No gaps.
- **Placeholder scan:** all code blocks are complete file/rule contents; no TBDs.
- **Type consistency:** class names identical across Task 1 Step 1 (SCSS), Task 1 Step 4 (rename table), Task 2 Step 1 (TSX), Task 2 Step 2 (scoped rule). Props signature unchanged from the existing parent call site.
