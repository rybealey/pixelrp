# Wulez clothing pack

Custom clothing from [Wulles/Wuco](https://github.com/Wulles/Wuco) ("Wulez
Clothes", last updated 2021-01-05): retro clothing from HabboCity and other
Brazilian hotels. Imported on 2026-10-16: 761 libraries, 763 figure sets and
749 Clothing Store rows (migrations 262 and 263, the second adding
face_U_rise2). See
`docker/nitro/import-wulez-clothes.py` for what was taken and why.

`ids.csv` maps every imported set and part from its pack id to its hotel id.
Everything was renumbered from 300000 up, because Habbo has since released
items on some of the pack's numbers.

## Reproducing it

The script can be re-run on the current tree. `ids.csv` tells it what it
already imported, so those pieces keep their ids and anything new takes the
next ones. Give each run a new migration number; it writes only the new rows.

```bash
git clone --depth 1 https://github.com/Wulles/Wuco.git wuco
curl -o fm_0806.xml https://images.habbo.com/gordon/flash-assets-PRODUCTION-202608061512-663981953/figuremap.xml

# 1. which SWFs to convert
python3 docker/nitro/import-wulez-clothes.py --wuco wuco --habbo-figuremap fm_0806.xml --list > libs.txt

# 2. copy those SWFs into a nitro-converter work dir's assets/swf/figure/,
#    repairing the eighteen broken ones first (see below), then convert
python3 docker/nitro/wulez-clothes/repair-swf.py in.swf out.swf
node ../nitro-converter/dist/Main.js --convert-swf

# 3. write the bundles, gamedata fragments, figuredata.xml and migration
python3 docker/nitro/import-wulez-clothes.py --wuco wuco \
    --bundles <work dir>/assets/bundled/figure --habbo-figuremap fm_0806.xml --migration 262
```

## Broken SWFs in the pack

- **Six lost their zlib checksum**: `acc_chest_U_squirtl3`, `acc_eye_U_bleed`,
  `acc_eye_U_holloweyes1234`, `acc_face_U_mouthsc`, `hat_U_bicol` and
  `hat_U_zebra`. The converter fails with "unexpected end of file", but the
  whole body is there.
- **Twelve kept another document class**: `shirt_M_chemisehbt` and the eleven
  `shirt_M_long*` shirts still name themselves `shirt_M_longamerics` and so on.
  They convert to empty bundles.
- **One is empty**: `acc_print_U_sheep.swf` is 24 bytes. It cannot be
  recovered, so it is not imported.

`repair-swf.py` fixes the first two kinds.
