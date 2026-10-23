# October 22 clothing

Custom clothing from another retro hotel's figure folder (`~/Downloads/clothing`
on 2026-10-22): 4,449 `.nitro` figure bundles with that hotel's
`_FigureMap.json` and `_FigureData.json`. Imported on 2026-10-22: 1,015
libraries, 1,018 figure sets and 983 Clothing Store rows, all at 50 credits
(migration 303). Every piece is sellable in the store, the one face included
- its Head tab lists faces since this import.

`ids.csv` maps every imported set and part from its source id to its hotel id,
in the block from 500000 (Wulez is 300000 up; the withdrawn Habzone import
was 400000-401792). Sets built here for libraries the source gave no set
appear as `syn<part id>`.

Much of the folder is the same retro packs as the withdrawn Habzone dump
(2,927 bundle names in common). This import was rendered before it shipped,
which the Habzone one was not.

## What was taken

| | |
| ---: | --- |
| 790 | sets from the source's FigureData |
| 228 | sets built for libraries the source never gave one - nobody could wear them there; one set per set type, part ids layered, colourable where the sprites are greyscale |
| 81 | source sets dropped as duplicates of another |

Of the libraries the hotel did not have by name, 29 are pixel copies of
hotel items, 7 are on `skip.txt` and 15 are the source's base libraries; the
other 29 have no bundle, duplicate another library's parts, draw none of
their own or are worn by no set.

## How it was checked

Through the repo's imager (Nitro's avatar code), every set at all eight
directions, once from the source hotel exactly as it was and once with this
import merged in, diffed pixel by pixel:

- 787 of 790 source sets draw exactly as they did in the source. The other
  three are better here: `hat_U_tv24gorrala` draws a cap the source drew
  nothing for, `habbox_france_NewBalance` its own shoe rather than another
  library's under the same id, and `bsstonino_U_maglianuova` differs by 19
  pixels at one direction.
- all 228 built sets draw;
- 34,267 spritesheet frames point at the same rectangle as the source's;
- the client's sleeve lookup, simulated for every shirt and jacket: 31 draw
  an arm at some directions only, and each is a design (strappy and
  off-shoulder tops, dresses, wings, capes, a plushie held in one hand) -
  checked by eye.

`skip.txt` holds the seven libraries that drew less here than in the source:
two of its libraries draw one part id, and the source showed whichever loaded
first.

## Reproducing it

```bash
curl -o fm_0806.xml https://images.habbo.com/gordon/flash-assets-PRODUCTION-202608061512-663981953/figuremap.xml
python3 docker/nitro/import-nitro-clothes.py --figures ~/Downloads/clothing \
    --figuremap ~/Downloads/clothing/_FigureMap.json --figuredata ~/Downloads/clothing/_FigureData.json \
    --ids docker/nitro/clothing-oct22/ids.csv --first-id 500000 --name ClothingOct22 \
    --about "custom clothing from another retro hotel's figure folder (October 2026)" \
    --skip docker/nitro/clothing-oct22/skip.txt --habbo-figuremap fm_0806.xml [--list | --migration 303]
```

A re-run on the current tree changes nothing. Pillow is needed for the
sprite fingerprints.

The Habzone removal list (`nitro/overrides/gamedata-remove/habzone-clothes.json`)
named 349 of these libraries and would have deleted their bundles on every
deploy; its library and bundle lists are emptied (it had done its job on
beta), its set ids kept.
