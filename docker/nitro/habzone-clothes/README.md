# Habzone clothing

**Withdrawn on 2026-10-17.** Too many pieces drew wrongly on beta, so the
whole import was taken back out: its bundles, FigureMap and FigureData entries,
emulator/Config/figuredata.xml sets and shelf rows (migration 267). Beta's
merged gamedata and asset tree lose them through
`nitro/overrides/gamedata-remove/habzone-clothes.json`. The importer and
`ids.csv` stay, so a later re-import gives every set the id it had (players
keep what they bought in user_clothing). Before re-importing, see "What went
wrong on beta" below.

## What went wrong on beta

The deploy merges gamedata fragments add-only: a set or library already on
the server is never replaced. The first deploy put the import's sets on beta;
the fixes after it changed their part ids, which reached the bundles (rsync
overwrites them) but not beta's FigureData, which kept the first part ids. So
beta's sets pointed at sprites the new bundles no longer had. A re-import must
either keep every part id it ships the first time, or remove its entries
(`gamedata-remove/`) and add them back in a later deploy.

Custom clothing from a Habzone asset dump (habzone.lol, a Nitro hotel; its
figure bundles and gamedata date from March 2024). Imported on 2026-10-17:
1,738 libraries, 1,793 figure sets and 1,737 Clothing Store rows (migrations
264, 265 and 266; the last two add acc_waist_F_per and hair_F_leetttbeyh). See `docker/nitro/import-habzone-clothes.py` for what was taken and
why.

`ids.csv` maps every imported set and part from its Habzone id to its hotel
id. Everything was renumbered from 400000 up (Wulez holds 300000 up), because
Habbo has since released items on many of the dump's numbers.

## What was left out

Of the dump's 5,151 figure bundles, about 2,700 are libraries the hotel
already has by name. Of the rest:

| skipped | why |
| ---: | --- |
| 254 | avatar effects (in the dump's EffectMap) - not clothing |
| 210 | copies: every main part's sprites are pixel-identical to a part the hotel already draws (a renamed Habbo or Wulez item) |
| 139 | in no FigureMap entry, so nothing could wear them on Habzone either: loose props (`HoloRPGun`, `FishingRod`, `MedicalKit`), `HabboCity_clothes_*` sheets, a few clothes |
| 77 | the same parts as an earlier library in the dump (duplicate libraries) |
| 15 | the dump's own base libraries (`hh_human_50_*`) |
| 13 | bundles that draw none of the parts their FigureMap entry lists |
| 10 | libraries no FigureData set wears |

`--list` prints every skipped library with its reason.

## Reproducing it

The bundles are already `.nitro`; nothing is converted. Pillow is needed for
the sprite fingerprints.

```bash
curl -o fm_0806.xml https://images.habbo.com/gordon/flash-assets-PRODUCTION-202608061512-663981953/figuremap.xml

# what would be taken, and why the rest is not
python3 docker/nitro/import-habzone-clothes.py --source <dump root> --habbo-figuremap fm_0806.xml --list

# write the bundles, gamedata fragments, figuredata.xml and migration
python3 docker/nitro/import-habzone-clothes.py --source <dump root> --habbo-figuremap fm_0806.xml --migration 264
```

`<dump root>` holds `bundled/figure/` and `gamedata/` (FigureMap.json,
FigureData.json, EffectMap.json). A re-run on the current tree changes
nothing; give a run that finds more a new migration number.

## Two sprite scales

The dump's spritesheets hold each sprite twice: `h_std_ch_4031_2_0` for the
full-size avatar and `sh_std_ch_4031_2_0` for the small one. The first
import's frame renaming read the `h_std_...` inside `sh_std_...` and dropped
the `s`, so in 323 bundles a small frame overwrote its full-size twin: shirts
drew only their sleeves and hairs a few stray strands, on the avatar and in
the store. Fixed the same day; ids did not change. The sprite pattern now
reads the scale, and fingerprints compare full-size sprites only.

Browsers keep a figure bundle for a week, so a fix to a bundle that already
shipped reaches players only once `avatar.asset.url`'s `?v=` is bumped in the
server's renderer-config.json (or they hard-reload).

## Render sweep (2026-10-17)

Every imported set was rendered at all eight directions through the repo's
imager (Nitro's avatar code) twice - once from the dump exactly as Habzone
served it, once from ours - and the two images diffed. That found three more
faults, all fixed in the importer:

- **One id per dump id.** A shirt is ch, ls and rs all on one id, and for a
  mirrored direction Nitro draws a left sleeve with the right sleeve's sprite
  under the same id. Renumbering each part type separately lost a sleeve or
  an arm facing left. Part ids are now shared per dump id; set ids, which is
  what players own, did not change.
- **Mirrored-only parts.** Some left parts have no sprites of their own and
  only ever drew mirrored (jacket_U_globocorazon's second balloon). They were
  dropped as drawing nothing; they are now kept.
- **Parts drawn by a sibling library.** Nitro loads every library the map
  lists for a set and finds each sprite across all of them, so a part its own
  library lacks still drew if another of them had it. Those are now claimed
  from the library that draws them.

What still differs (46 of 1,793) is the dump's own id collisions: two of its
libraries draw the same id, and Habzone showed whichever loaded first
(hat_U_lion showed hat_U_panda, shirt_M_Rapto a plain crop top). Ours draws
each library's own art.

## Stray sprites

Each bundle keeps only the parts it was imported for, under their new ids;
3,134 other sprites were removed. Nitro looks an avatar sprite up by name
across every library it has loaded and uses the first it finds, so a sprite
left under an old id would draw over whatever the hotel has on that id.
