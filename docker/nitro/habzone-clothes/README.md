# Habzone clothing

Custom clothing from a Habzone asset dump (habzone.lol, a Nitro hotel; its
figure bundles and gamedata date from March 2024). Imported on 2026-10-17:
1,737 libraries, 1,791 figure sets and 1,735 Clothing Store rows (migration
264). See `docker/nitro/import-habzone-clothes.py` for what was taken and
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

## Stray sprites

Each bundle keeps only the parts it was imported for, under their new ids;
3,134 other sprites were removed. Nitro looks an avatar sprite up by name
across every library it has loaded and uses the first it finds, so a sprite
left under an old id would draw over whatever the hotel has on that id.
