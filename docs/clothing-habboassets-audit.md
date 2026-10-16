# Clothing vs HabboAssets

Audit of 2026-10-16: every clothing library on
[habboassets.com/swfs/clothing](https://www.habboassets.com/swfs/clothing)
checked against the hotel. The full list is in
[clothing-habboassets.csv](clothing-habboassets.csv), one row per HabboAssets
library.

## One name everywhere

A clothing item has the same name in four places: HabboAssets, Habbo's
`figuremap.xml`, our `FigureMap.json`, and the bundle file
(`<library>.nitro`). Since migration 260, `catalog_clothing.clothing_name` uses it
too. It lists one library per set, in `clothing_parts` order. For example,
`6611,6612` is `shirt_M_paintoutfit,shirt_F_paintoutfit`. To look up a store
row on HabboAssets, open `/swfs/clothing/<library>`.

Shelf labels are unchanged: the store shows `display_name`.
`user_clothing.part` holds the owned set's own library.

The mapping from set to library comes from
`docker/nitro/gen-clothing-habbo-names.py`. To check it independently: the
script and migrations 156–158 (which mapped sets from the server's real
FigureMap) both mapped 2,574 sets, and they agree on every one.

## Coverage

| status | libraries | meaning |
|---|---:|---|
| imported | 2,987 | in our FigureMap and used by a set in `figuredata.xml` |
| figuredata only | 22 | the set is in `figuredata.xml`, but the library is not in the FigureMap rebuilt from the repo (see below) |
| library only | 18 | in our FigureMap, but no set draws from it |
| missing | 5 | in Habbo's current figuremap, not in the hotel |
| retired | 89 | no longer in Habbo's figuremap |

"Our FigureMap" is rebuilt from the repo: Habbo's figuremap from build
`202608061512` (the one the 2026-08-07 conversion used) plus the 47 libraries
in `nitro/overrides`. The live file is `nitro/assets/gamedata/FigureMap.json`
on the server, which is not in git.

### Figuredata only: check on beta

These are the 22 sets from the academia and Halloween wave that
`38_ImportedClothingGates.sql` added on 2026-08-28: `acc_chest_U_vintagebag`,
`acc_head_U_ducketleafcrown`, `acc_head_U_skeletalheadband`,
`face_U_academiagothicmakeup`, `face_U_academiagothicmakeup2`,
`hair_U_academiadollhairdo`, `hair_U_wizardcurls`, `hat_U_batonesie`,
`jacket_F_studentcardigan`, `jacket_M_studentcardigan`, `jacket_F_wizardgarb`,
`jacket_M_wizardgarb`, `misc_U_ruffledcuffs`, `misc_U_wand`,
`shirt_U_batonesie`, `shoes_U_loosesocks`, and the pets `pet_U_batfriend`,
`pet_U_hauntedpuppet`, `pet_U_persiancat`, `pet_U_possessedpumpkin`,
`pet_U_raven` and `pet_U_tinyowl`.

Their bundles are not in `nitro/overrides`, so they are only drawn if the live
FigureMap and `bundled/figure/` on the server have them. Check on the VPS:

```bash
cd /opt/pixelrp-beta && for l in acc_chest_U_vintagebag hair_U_wizardcurls pet_U_raven; do grep -q "\"$l\"" nitro/assets/gamedata/FigureMap.json && echo "$l map" ; ls nitro/assets/bundled/figure/$l.nitro; done
```

### Missing

| library | Habbo sets | notes |
|---|---|---|
| `hat_U_autumnberet2` | 6549 | **not imported**: a real gap |
| `hat_U_nftbananahelmet` | 6609 | Habbo's later copy of `hat_U_bananahelmet`, which we have as set 6609. Covered |
| `face_U_nftdeterminedface2` | none live | no sets in Habbo's figuredata yet |
| `face_U_nfthopefulface2` | none live | no sets in Habbo's figuredata yet |
| `jacket_U_nfttasselvest` | none live | no sets in Habbo's figuredata yet |

### Library only

Test and placeholder libraries (`face_U_test`, `hat_U_23test2/3/6`,
`jacket_U_animtest`, `jacket_U_CCtest`, `jacket_U_CCtest2`, `pet_U_shiba1test`,
`Shirt_F_Tshirt_Plain`) and a few with no set in Habbo's figuredata either
(`acc_eye_U_cyeyepiece`, `acc_face_U_pipe`, `face_F/M_nftscarface2`,
`jacket_U_firedemon`, `jacket_U_nftbiglollipop`,
`jacket_U_snowwar4_team1/2`, `trousers_U_nft2023skirt`). There is nothing to
sell.

### Retired

Libraries Habbo has since dropped from its figuremap. Most were renamed: the
`jacket_U_*` held items became `misc_U_*` (`jacket_U_mittens` →
`misc_U_mittens`), and the sets went with them. HabboAssets lists no live sets
for any of them.

## Not on HabboAssets

Six sets in `figuredata.xml` belong to no Habbo library:
`acc_head_U_ribbonshnibbony` (19792140), `acc_chest_U_Chrome` (80000103),
`hair_U_cookiedana` (100021462), `hat_U_pufflehat` (140675345),
`hair_U_britpigtails` (140952645) and `hat_U_chiikawahat` (348919373). Their
store rows keep the names migration 156 gave them. Twenty old hair sets
(120–810) have no part that any figuremap maps.

## Found along the way

`catalog_clothing` row `clothing_tshirt_rolled` (Rolledtee, id 32 in the
original dump) lists sets `3323,335`. `335` is a truncated `3351`
(`shirt_F_tshirt_rolled`), so the female half was never part of that row.
Migration 156's backfill then gave 3351 a listing of its own
(`shirt_F_tshirt_rolled`). Migration 260 leaves that row alone and lists it in
its receipt.
