# Corporations Window Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Corporations window per `docs/superpowers/specs/2026-08-30-corps-window-polish-design.md` — identity header, restyled rank ladder, presence legend, overlay settings drawer, skeleton/empty states, 640x480 frame.

**Architecture:** Client-only change confined to the `rp-corporations` component pair. Task 1 lands the complete new TSX markup (new DOM structure, on-duty computation, status dots, overlay drawer placement, skeleton and empty states). Task 2 lands the complete new SCSS. Task 3 adds the player-facing changelog entry and the final verification pass.

**Tech Stack:** React 18 + TypeScript (nitro-react client), SCSS, Vite. No server/emulator changes.

## Global Constraints

- Branch: `beta`. Commit locally; do NOT push — the user deploys and tests in-game themselves.
- The client has no test suite. The verification cycle for every task is `yarn build` from `client/` completing without errors.
- No em-dashes or middots in any client-visible string (Habbo font renders them as a music note); plain hyphens only. (CHANGELOG.md is web-facing and may use em-dashes in headings, matching existing entries.)
- Pixel art (badges, avatar sprites) renders at native size, never scaled: `image-rendering: pixelated`, `background-size: auto` semantics preserved exactly as in the current files.
- Dark surfaces would require `--prp-chrome-*` vars, but this window is light-surface; the chrome vars are used only for tint accents, as specified.
- The rank ladder (`.rp-corps-ranks`) remains the window's ONE scroller; content-area overflow stays hidden.

---

### Task 1: New window markup (TSX)

**Files:**
- Modify: `client/src/components/rp-corporations/RpCorporationsView.tsx` (full replacement below)

**Interfaces:**
- Consumes: existing packets/parsers (`RpCorpsEvent`, `RpCorpDetailEvent`, `RpGetCorpsComposer`, `RpGetCorpDetailComposer`) and `RpProfileState` — all unchanged.
- Produces: the class names Task 2 styles: `rp-corps-main`, `rp-corps-head`, `rp-corps-badge-plate`, `rp-corps-head-info`, `rp-corps-title`, `rp-corps-sub`, `rp-corps-chips`, `rp-corps-chip`, `rp-corps-chip-value`, `rp-corps-chip-label`, `rp-corps-legend`, `rp-corps-legend-item`, `rp-corps-dot` (+ `is-offline`/`is-online`/`is-onduty`), `rp-corps-body`, `rp-corps-panel` (+ `is-open`), `rp-corps-panel-title`, `rp-corps-check`, `rp-corps-ranks`, `rp-corps-rank`, `rp-corps-rank-row`, `rp-corps-rank-name`, `rp-corps-rank-pay`, `rp-corps-rank-none`, `rp-corps-employees`, `rp-corps-employee`, `rp-corps-employee-status`, `rp-corps-employee-portrait` (+ `is-online`/`is-onduty`), `rp-corps-employee-info`, `rp-corps-employee-name-row`, `rp-corps-employee-name`, `rp-corps-employee-tier`, `rp-corps-employee-shifts`, `rp-corps-skeleton`, `rp-corps-skeleton-bar`, `rp-corps-skeleton-cards`, `rp-corps-skeleton-card`, `rp-corps-none`, `rp-corps-none-text`, plus the unchanged rail classes (`rp-corps-rail`, `rp-corps-rail-tool`, `rp-corps-rail-item`).

- [ ] **Step 1: Replace the component file**

Write this exact content to `client/src/components/rp-corporations/RpCorporationsView.tsx`:

```tsx
import { ILinkEventTracker, RpCorpDetailEvent, RpCorpEntry, RpCorpRank, RpCorpsEvent, RpGetCorpDetailComposer, RpGetCorpsComposer } from '@nitrots/nitro-renderer';
import { FC, useEffect, useState } from 'react';
import { LuSlidersHorizontal } from 'react-icons/lu';
import { AddEventLinkTracker, CreateLinkEvent, RemoveLinkEventTracker, SendMessageComposer } from '../../api';
import { LayoutAvatarImageView, LayoutBadgeImageView, NitroCardContentView, NitroCardHeaderView, NitroCardView } from '../../common';
import { useMessageEvent } from '../../hooks';
import { RpProfileState } from '../rp-profile/RpProfileState';

// PixelRP Corporations window, opened from the side drawer's Corporations
// button (CreateLinkEvent('rp-corporations/toggle')). Viewable by every
// player: corp rail on the left (badge per corp, NPH17 default), then the
// selected corp's identity header (badge plate, name, description, stat
// chips) above its rank ladder (highest rank first) with pay per 10 minutes
// of shift worked and the employees holding each rank (tier I-V).

const DEFAULT_CORP_BADGE: string = 'NPH17';
const TIER_NUMERALS: string[] = [ 'I', 'II', 'III', 'IV', 'V' ];

interface CorpDetail
{
    id: number;
    name: string;
    badge: string;
    description: string;
    employeeCount: number;
    // quantity the corporation holds; 0 everywhere until farming lands
    stock: number;
    ranks: RpCorpRank[];
}

export const RpCorporationsView: FC<{}> = props =>
{
    const [ isVisible, setIsVisible ] = useState(false);
    const [ corps, setCorps ] = useState<RpCorpEntry[]>([]);
    const [ selectedId, setSelectedId ] = useState<number>(0);
    const [ detail, setDetail ] = useState<CorpDetail>(null);
    // The rail's slider button opens the display-options drawer. It overlays
    // the roster (no reflow) and holds the show-on-cards toggles.
    const [ panelOpen, setPanelOpen ] = useState(false);
    const [ showWeekly, setShowWeekly ] = useState(true);
    const [ showTotal, setShowTotal ] = useState(true);

    useMessageEvent<RpCorpsEvent>(RpCorpsEvent, event =>
    {
        const entries = event.getParser().corps;

        setCorps(entries);
        // auto-open the first corp so the window never sits empty
        setSelectedId(prevValue => (entries.some(entry => (entry.id === prevValue)) ? prevValue : (entries[0]?.id ?? 0)));
    });

    useMessageEvent<RpCorpDetailEvent>(RpCorpDetailEvent, event =>
    {
        const parser = event.getParser();

        setDetail({ id: parser.corpId, name: parser.name, badge: parser.badge, description: parser.description, employeeCount: parser.employeeCount, stock: parser.stock, ranks: parser.ranks });
    });

    useEffect(() =>
    {
        if(!isVisible) return;

        SendMessageComposer(new RpGetCorpsComposer());
    }, [ isVisible ]);

    useEffect(() =>
    {
        if(!isVisible || !selectedId) return;

        SendMessageComposer(new RpGetCorpDetailComposer(selectedId));
    }, [ isVisible, selectedId ]);

    useEffect(() =>
    {
        const linkTracker: ILinkEventTracker = {
            linkReceived: (url: string) =>
            {
                const parts = url.split('/');

                if(parts.length < 2) return;

                switch(parts[1])
                {
                    case 'show':
                        setIsVisible(true);
                        return;
                    case 'hide':
                        setIsVisible(false);
                        return;
                    case 'toggle':
                        setIsVisible(prevValue => !prevValue);
                        return;
                }
            },
            eventUrlPrefix: 'rp-corporations/'
        };

        AddEventLinkTracker(linkTracker);

        return () => RemoveLinkEventTracker(linkTracker);
    }, []);

    if(!isVisible) return null;

    const shownDetail = ((detail && (detail.id === selectedId)) ? detail : null);
    // highest rank first, like a real org chart
    const ranks = (shownDetail ? [ ...shownDetail.ranks ].sort((a, b) => (b.order - a.order)) : []);
    // computed client-side: the roster already carries every employee's flag
    const onDutyCount = (shownDetail ? shownDetail.ranks.reduce((total, rank) => (total + rank.employees.filter(employee => employee.onDuty).length), 0) : 0);

    return (
        <NitroCardView uniqueKey="rp-corporations" className="rp-corporations-window" theme="primary-slim">
            <NitroCardHeaderView headerText="Corporations" onCloseClick={ () => setIsVisible(false) } />
            <NitroCardContentView overflow="hidden" className="text-black">
                <div className="rp-corps-layout">
                    <div className="rp-corps-rail">
                        { /* opens the display-options drawer; sits above the corp
                             badges with a divider so it reads as a control, not
                             another corporation */ }
                        <div className={ `rp-corps-rail-tool ${ panelOpen ? 'is-active' : '' }` }
                            title="Display options"
                            onClick={ () => setPanelOpen(value => !value) }>
                            <LuSlidersHorizontal />
                        </div>
                        { corps.map(corp => (
                            <div key={ corp.id } title={ corp.name }
                                className={ `rp-corps-rail-item ${ (corp.id === selectedId) ? 'is-active' : '' }` }
                                onClick={ () => setSelectedId(corp.id) }>
                                <LayoutBadgeImageView badgeCode={ corp.badge || DEFAULT_CORP_BADGE } />
                            </div>
                        )) }
                    </div>
                    <div className="rp-corps-main">
                        { shownDetail &&
                            // keyed by corp so switching remounts the block and
                            // replays the fade-in
                            <div key={ shownDetail.id } className="rp-corps-detail">
                                <div className="rp-corps-head">
                                    <div className="rp-corps-badge-plate">
                                        <LayoutBadgeImageView badgeCode={ shownDetail.badge || DEFAULT_CORP_BADGE } />
                                    </div>
                                    <div className="rp-corps-head-info">
                                        <div className="rp-corps-title">{ shownDetail.name }</div>
                                        { shownDetail.description &&
                                            <div className="rp-corps-sub">{ shownDetail.description }</div> }
                                    </div>
                                    <div className="rp-corps-chips">
                                        <div className="rp-corps-chip">
                                            <span className="rp-corps-chip-value">{ shownDetail.employeeCount }</span>
                                            <span className="rp-corps-chip-label">Employees</span>
                                        </div>
                                        <div className="rp-corps-chip">
                                            <span className="rp-corps-chip-value">{ onDutyCount }</span>
                                            <span className="rp-corps-chip-label">On duty</span>
                                        </div>
                                        <div className="rp-corps-chip">
                                            <span className="rp-corps-chip-value">{ shownDetail.stock }</span>
                                            <span className="rp-corps-chip-label">Stock</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="rp-corps-legend">
                                    <span className="rp-corps-legend-item"><i className="rp-corps-dot is-offline" />Offline</span>
                                    <span className="rp-corps-legend-item"><i className="rp-corps-dot is-online" />Online</span>
                                    <span className="rp-corps-legend-item"><i className="rp-corps-dot is-onduty" />On duty</span>
                                </div>
                                <div className="rp-corps-body">
                                    { /* overlay drawer: floats over the roster's left
                                         edge, so the three-column grid never reflows */ }
                                    <div className={ `rp-corps-panel ${ panelOpen ? 'is-open' : '' }` }>
                                        <div className="rp-corps-panel-title">Show on cards</div>
                                        <label className="rp-corps-check">
                                            <input type="checkbox" checked={ showWeekly } onChange={ event => setShowWeekly(event.target.checked) } />
                                            <span>Weekly shifts</span>
                                        </label>
                                        <label className="rp-corps-check">
                                            <input type="checkbox" checked={ showTotal } onChange={ event => setShowTotal(event.target.checked) } />
                                            <span>Total shifts</span>
                                        </label>
                                    </div>
                                    { /* clicking the roster dismisses the drawer */ }
                                    <div className="rp-corps-ranks" onClick={ () => panelOpen && setPanelOpen(false) }>
                                        { ranks.map(rank => (
                                            <div key={ rank.id } className="rp-corps-rank">
                                                <div className="rp-corps-rank-row">
                                                    <span className="rp-corps-rank-name">{ rank.name }</span>
                                                    <span className="rp-corps-rank-pay">{ rank.pay }c <small>/ 10 min</small></span>
                                                </div>
                                                { (rank.employees.length === 0) &&
                                                    <div className="rp-corps-rank-none">No employees</div> }
                                                { (rank.employees.length > 0) &&
                                                    <div className="rp-corps-employees">
                                                        { rank.employees.map(employee =>
                                                        {
                                                            const tierLabel = ((rank.tiers > 0) ? TIER_NUMERALS[Math.min(Math.max(employee.tier, 1), rank.tiers) - 1] : null);
                                                            const rankLabel = (tierLabel ? `${ rank.name } ${ tierLabel }` : rank.name);
                                                            const statusWord = (employee.onDuty ? 'On duty' : (employee.online ? 'Online' : 'Offline'));

                                                            return (
                                                                <div key={ employee.username } className="rp-corps-employee" title={ `${ rankLabel } - ${ statusWord }` }
                                                                    onClick={ () =>
                                                                    {
                                                                        RpProfileState.name = employee.username;
                                                                        RpProfileState.figure = employee.figure;
                                                                        RpProfileState.motto = '';
                                                                        RpProfileState.online = employee.online;
                                                                        // The roster carries no user id, but we are
                                                                        // looking at this player's employment right
                                                                        // now - hand it over rather than look it up.
                                                                        RpProfileState.userId = 0;
                                                                        // the roster carries no rank, so no verified mark
                                                                        RpProfileState.staff = false;
                                                                        RpProfileState.employment = {
                                                                            corpId: shownDetail.id,
                                                                            badge: (corps.find(entry => (entry.id === shownDetail.id))?.badge ?? ''),
                                                                            corpName: shownDetail.name,
                                                                            rankName: rank.name,
                                                                            tier: ((rank.tiers > 0) ? employee.tier : 0)
                                                                        };
                                                                        CreateLinkEvent('rp-profile/show');
                                                                    } }>
                                                                    { /* second presence signal beside the tint, for
                                                                         colorblind legibility */ }
                                                                    <span className={ `rp-corps-dot rp-corps-employee-status ${ employee.onDuty ? 'is-onduty' : (employee.online ? 'is-online' : 'is-offline') }` } />
                                                                    { /* portrait tint doubles as the presence signal:
                                                                         gray offline, green online, blue on duty */ }
                                                                    <div className={ `rp-corps-employee-portrait${ employee.onDuty ? ' is-onduty' : (employee.online ? ' is-online' : '') }` }>
                                                                        <LayoutAvatarImageView figure={ employee.figure } direction={ 2 } />
                                                                    </div>
                                                                    <div className="rp-corps-employee-info">
                                                                        <div className="rp-corps-employee-name-row">
                                                                            <span className="rp-corps-employee-name">{ employee.username }</span>
                                                                            { tierLabel &&
                                                                                <span className="rp-corps-employee-tier">{ tierLabel }</span> }
                                                                        </div>
                                                                        { /* hardcoded zeros until the server sends shift stats */ }
                                                                        { (showWeekly || showTotal) &&
                                                                            <div className="rp-corps-employee-shifts">
                                                                                { [ showWeekly && 'Wk 0', showTotal && 'Total 0' ].filter(Boolean).join(' / ') }
                                                                            </div> }
                                                                    </div>
                                                                </div>
                                                            );
                                                        }) }
                                                    </div> }
                                            </div>
                                        )) }
                                    </div>
                                </div>
                            </div> }
                        { !shownDetail && (corps.length > 0) &&
                            <div className="rp-corps-skeleton">
                                <div className="rp-corps-skeleton-bar" />
                                <div className="rp-corps-skeleton-cards">
                                    <div className="rp-corps-skeleton-card" />
                                    <div className="rp-corps-skeleton-card" />
                                    <div className="rp-corps-skeleton-card" />
                                </div>
                            </div> }
                        { !corps.length &&
                            <div className="rp-corps-none">
                                <LayoutBadgeImageView badgeCode={ DEFAULT_CORP_BADGE } />
                                <div className="rp-corps-none-text">No corporations yet.</div>
                            </div> }
                    </div>
                </div>
            </NitroCardContentView>
        </NitroCardView>
    );
}
```

- [ ] **Step 2: Verify the build passes**

Run from `client/`: `yarn build`
Expected: completes without TypeScript or Vite errors. (The SCSS still styles the old class names; the window will look unstyled until Task 2 — that is expected at this commit.)

- [ ] **Step 3: Commit**

```bash
git add client/src/components/rp-corporations/RpCorporationsView.tsx
git commit -m "feat(corps): new window markup - identity header, legend, overlay drawer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: New stylesheet (SCSS)

**Files:**
- Modify: `client/src/components/rp-corporations/RpCorporationsView.scss` (full replacement below)

**Interfaces:**
- Consumes: every class name listed in Task 1's Produces block; global SCSS tokens `$white`, `$border-radius`; CSS var `--prp-chrome-solid`.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Replace the stylesheet**

Write this exact content to `client/src/components/rp-corporations/RpCorporationsView.scss`:

```scss
// Corporations window: badge rail on the left, then the selected corp's
// identity header (chrome-tinted badge plate, name, stat chips) above its
// scrolling rank ladder. Fixed 640x480; the ladder is the ONE scroller
// (content-area overflow is hidden so it can't double-scroll).

// Presence palette - shared by the portrait tints, the card status dots and
// the legend so the three signals can never drift apart.
$corps-presence-offline: #b0b0b0;
$corps-presence-online: #2e9e4f;
$corps-presence-onduty: #2f7fd6;

// Coin gold for the rank pay chips.
$corps-coin-text: #8a6d1d;
$corps-coin-fill: rgba(240, 195, 80, 0.18);
$corps-coin-border: rgba(200, 160, 60, 0.45);

// Loading ghosts share one shimmer treatment.
%rp-corps-shimmer {
    border-radius: 6px;
    background: linear-gradient(90deg, rgba(0, 0, 0, 0.05) 25%, rgba(0, 0, 0, 0.1) 50%, rgba(0, 0, 0, 0.05) 75%);
    background-size: 200% 100%;
    animation: rp-corps-shimmer 1.2s linear infinite;
}

@keyframes rp-corps-shimmer {
    to { background-position: -200% 0; }
}

@keyframes rp-corps-fade {
    from { opacity: 0; }
}

.nitro-card.rp-corporations-window {
    width: 640px;
    height: 480px;

    .rp-corps-layout {
        display: flex;
        gap: 10px;
        flex: 1;
        min-height: 0;
    }

    .rp-corps-rail {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding-right: 8px;
        border-right: 1px solid rgba(0, 0, 0, 0.08);
        overflow-y: auto;
        flex-shrink: 0;
    }

    .rp-corps-rail-item {
        width: 48px;
        height: 48px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: $border-radius;
        background: rgba(0, 0, 0, 0.04);
        border: 1px solid rgba(0, 0, 0, 0.1);
        cursor: pointer;
        transition: border-color 0.1s ease, background 0.1s ease;

        &:hover { border-color: rgba(0, 0, 0, 0.25); }

        &.is-active {
            border-color: var(--prp-chrome-solid);
            background: color-mix(in srgb, var(--prp-chrome-solid) 14%, transparent);
        }

        .badge-image {
            position: static;
            width: 40px;
            height: 40px;
            background-repeat: no-repeat;
            background-position: center;
            image-rendering: pixelated;
        }
    }

    // Rail control: same square as a corp badge, but divided off below so it
    // reads as a tool rather than another corporation.
    .rp-corps-rail-tool {
        width: 48px;
        height: 48px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        border-radius: $border-radius;
        background: rgba(0, 0, 0, 0.04);
        border: 1px solid rgba(0, 0, 0, 0.1);
        color: rgba(0, 0, 0, 0.45);
        cursor: pointer;
        margin-bottom: 2px;
        padding-bottom: 0;
        border-bottom: 1px solid rgba(0, 0, 0, 0.1);
        transition: border-color 0.1s ease, background 0.1s ease, color 0.1s ease;

        svg { width: 20px; height: 20px; }

        &:hover { border-color: rgba(0, 0, 0, 0.25); }

        // open: tinted with the player's chosen UI chrome colour
        &.is-active {
            border-color: var(--prp-chrome-solid);
            background: color-mix(in srgb, var(--prp-chrome-solid) 16%, transparent);
            color: var(--prp-chrome-solid);
        }
    }

    // Hosts whichever of the three states is showing (detail, skeleton, or
    // the no-corps empty state).
    .rp-corps-main {
        position: relative;
        flex: 1;
        min-width: 0;
        min-height: 0;
        display: flex;
        flex-direction: column;
    }

    .rp-corps-detail {
        flex: 1;
        min-width: 0;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        // remounted per corp (keyed), so switching replays this fade
        animation: rp-corps-fade 0.12s ease;
    }

    // ---- identity header ------------------------------------------------

    .rp-corps-head {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    // The corp's identity moment: native 40px badge art on a plate tinted
    // with the player's chrome colour. Art is never scaled.
    .rp-corps-badge-plate {
        width: 52px;
        height: 52px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        background: color-mix(in srgb, var(--prp-chrome-solid) 12%, transparent);
        border: 1px solid color-mix(in srgb, var(--prp-chrome-solid) 35%, transparent);

        .badge-image {
            position: static;
            width: 40px;
            height: 40px;
            background-repeat: no-repeat;
            background-position: center;
            image-rendering: pixelated;
        }
    }

    .rp-corps-head-info {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .rp-corps-title {
        font-size: 16px;
        font-weight: 700;
        line-height: 1.2;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .rp-corps-sub {
        font-size: 11px;
        color: rgba(0, 0, 0, 0.55);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    // Mini stat tiles: value over a tiny uppercase label.
    .rp-corps-chips {
        display: flex;
        gap: 6px;
        flex-shrink: 0;
    }

    .rp-corps-chip {
        min-width: 56px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1px;
        padding: 5px 8px 4px;
        border-radius: 6px;
        background: $white;
        border: 1px solid rgba(0, 0, 0, 0.1);
    }

    .rp-corps-chip-value {
        font-size: 13px;
        font-weight: 700;
        line-height: 1;
    }

    .rp-corps-chip-label {
        font-size: 8px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        color: rgba(0, 0, 0, 0.4);
    }

    // ---- presence -------------------------------------------------------

    .rp-corps-legend {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        font-size: 9px;
        color: rgba(0, 0, 0, 0.45);
    }

    .rp-corps-legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .rp-corps-dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex-shrink: 0;

        &.is-offline { background: $corps-presence-offline; }
        &.is-online { background: $corps-presence-online; }
        &.is-onduty { background: $corps-presence-onduty; }
    }

    // ---- roster body (ladder + overlay drawer) --------------------------

    .rp-corps-body {
        position: relative;
        flex: 1;
        min-height: 0;
        display: flex;
    }

    .rp-corps-ranks {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        overflow-y: auto;
        min-height: 0;
        padding-right: 2px;
    }

    // Rank header: quiet section label + coin pay chip over a hairline rule.
    .rp-corps-rank-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 0 3px;
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    }

    .rp-corps-rank-name {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        color: rgba(0, 0, 0, 0.5);
    }

    // Top of the ladder (ranks render highest-first): a short chrome bar on
    // the name so seniority reads at a glance.
    .rp-corps-rank:first-child .rp-corps-rank-name {
        border-left: 3px solid var(--prp-chrome-solid);
        padding-left: 5px;
        color: rgba(0, 0, 0, 0.65);
    }

    .rp-corps-rank-pay {
        font-size: 11px;
        font-weight: 700;
        padding: 1px 7px;
        border-radius: 8px;
        color: $corps-coin-text;
        background: $corps-coin-fill;
        border: 1px solid $corps-coin-border;

        small {
            font-weight: 400;
            color: rgba(0, 0, 0, 0.4);
        }
    }

    .rp-corps-rank-none {
        font-size: 10px;
        color: rgba(0, 0, 0, 0.35);
        padding: 4px 2px 0;
    }

    .rp-corps-employees {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 6px;
        padding: 6px 2px 2px;
    }

    // Employee card: mini HUD-style plate - masked portrait + name/tier +
    // shift stats. Clicking opens the player's RP profile.
    .rp-corps-employee {
        position: relative;
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        padding: 5px 8px 5px 5px;
        border-radius: $border-radius;
        background: $white;
        border: 1px solid rgba(0, 0, 0, 0.12);
        cursor: pointer;
        transition: border-color 0.12s ease, transform 0.12s ease, box-shadow 0.12s ease;

        &:hover {
            border-color: rgba(0, 0, 0, 0.3);
            transform: translateY(-1px);
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
        }

        &:active {
            transform: none;
            box-shadow: none;
        }
    }

    // second presence signal, pinned to the card corner (reuses .rp-corps-dot)
    .rp-corps-employee-status {
        position: absolute;
        top: 5px;
        right: 5px;
    }

    // Circular mask over the 90x130 sprite at native size (same technique as
    // the Player HUD portrait: no scaling, pixelated, the 2nd background-
    // position value frames the head + shoulders). The tint doubles as the
    // presence signal.
    .rp-corps-employee-portrait {
        flex-shrink: 0;
        position: relative;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        overflow: hidden;
        background: $corps-presence-offline;

        &.is-online { background: $corps-presence-online; }
        &.is-onduty { background: $corps-presence-onduty; }

        .avatar-image {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            background-size: auto;
            background-repeat: no-repeat;
            background-position: center -30px;
            image-rendering: -moz-crisp-edges;
            image-rendering: crisp-edges;
            image-rendering: pixelated;
        }
    }

    .rp-corps-employee-info {
        flex: 1;
        min-width: 0;
    }

    .rp-corps-employee-name-row {
        display: flex;
        align-items: center;
        gap: 5px;
        min-width: 0;
    }

    .rp-corps-employee-name {
        font-size: 12px;
        font-weight: 700;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .rp-corps-employee-tier {
        flex-shrink: 0;
        font-size: 9px;
        font-weight: 700;
        padding: 1px 4px;
        border-radius: 6px;
        background: rgba(0, 0, 0, 0.08);
        color: rgba(0, 0, 0, 0.6);
    }

    .rp-corps-employee-shifts {
        font-size: 10px;
        color: rgba(0, 0, 0, 0.45);
        white-space: nowrap;
    }

    // ---- overlay drawer -------------------------------------------------

    // Slides over the roster's left edge (inside the body, so it sits below
    // the header). The three-column grid never reflows.
    .rp-corps-panel {
        position: absolute;
        top: 0;
        left: 0;
        bottom: 0;
        width: 150px;
        z-index: 5;
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px;
        border-radius: 6px;
        background: $white;
        border: 1px solid rgba(0, 0, 0, 0.12);
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
        opacity: 0;
        transform: translateX(-8px);
        pointer-events: none;
        transition: opacity 0.16s ease, transform 0.16s ease;

        &.is-open {
            opacity: 1;
            transform: none;
            pointer-events: auto;
        }
    }

    .rp-corps-panel-title {
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.4px;
        text-transform: uppercase;
        color: rgba(0, 0, 0, 0.35);
    }

    .rp-corps-check {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        cursor: pointer;
        user-select: none;

        input {
            cursor: pointer;
            accent-color: var(--prp-chrome-solid);
        }
    }

    // ---- loading + empty states -----------------------------------------

    .rp-corps-skeleton {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 8px;
        animation: rp-corps-fade 0.12s ease;
    }

    .rp-corps-skeleton-bar {
        @extend %rp-corps-shimmer;
        height: 18px;
        width: 45%;
    }

    .rp-corps-skeleton-cards {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 6px;
    }

    .rp-corps-skeleton-card {
        @extend %rp-corps-shimmer;
        height: 54px;
    }

    .rp-corps-none {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;

        .badge-image {
            position: static;
            width: 40px;
            height: 40px;
            background-repeat: no-repeat;
            background-position: center;
            image-rendering: pixelated;
            opacity: 0.5;
        }
    }

    .rp-corps-none-text {
        font-size: 11px;
        color: rgba(0, 0, 0, 0.45);
    }
}
```

- [ ] **Step 2: Verify the build passes**

Run from `client/`: `yarn build`
Expected: completes without Sass or Vite errors.

- [ ] **Step 3: Sanity-grep for orphans**

Run from repo root:
`grep -n "is-single\|rp-corps-figures\|rp-corps-figure\b\|rp-corps-title-row\|rp-corps-count\|rp-corps-empty\|rp-corps-panel-inner" client/src/components/rp-corporations/RpCorporationsView.tsx client/src/components/rp-corporations/RpCorporationsView.scss`
Expected: no matches (all removed class names are gone from both files).

- [ ] **Step 4: Commit**

```bash
git add client/src/components/rp-corporations/RpCorporationsView.scss
git commit -m "style(corps): identity header, coin pay chips, overlay drawer, skeletons

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Changelog + final verification

**Files:**
- Modify: `CHANGELOG.md` (new dated section at the top, directly below the maintainer comment block)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing.

- [ ] **Step 1: Add the changelog entry**

Insert this section into `CHANGELOG.md` immediately after the closing `-->` of the maintainer comment block (above the current top entry). If a `## 2026-08-30 — ...` section from another change already sits at the top, place this new section above it:

```markdown
## 2026-08-30 — A sharper Corporations window

### Changed

- **Corporations got a proper front page.** Each corporation now opens with
  an identity header - its badge on a plate in your chosen UI colour, its
  description, and at-a-glance counts of employees, who's on duty right
  now, and stock. The window itself is roomier, so names stop getting cut
  off.
- **You can finally tell who's around.** A small legend explains the
  portrait colours (gray offline, green online, blue on duty), and every
  employee card carries a matching status dot.
- **Pay looks like pay.** Each rank's wage now sits in a little coin chip
  instead of plain text, and the top rank is marked so the ladder reads
  top-down at a glance.
- **The display-options drawer stopped shoving the roster around.** It now
  slides over the list instead of squeezing it into a single column.
```

- [ ] **Step 2: Final build + lint pass**

Run from `client/`: `yarn build && yarn eslint`
Expected: build completes; eslint reports no NEW errors in `src/components/rp-corporations/` (pre-existing warnings elsewhere in the codebase are not this change's problem).

- [ ] **Step 3: Commit (deploy-tagged)**

```bash
git add CHANGELOG.md
git commit -m "feat(corps): polish corporations window (bump client)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Do NOT push. The user reviews, pushes to `beta` (which they deploy via `gh workflow run deploy.yml`), and tests in-game per project preference.
