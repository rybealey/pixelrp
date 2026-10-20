# Nitro asset downloader

A script you run in the browser, on a Nitro hotel's game page, that saves the
hotel's furni into a folder on your computer:

- the furni files (`.nitro`)
- their icons, including each colour's own icon
- every sprite cut out of each furni, as separate PNGs
- badges

It finds everything the way the game does, from the site's own settings and
furni list, so it works on any site running the standard Nitro client.

## Running it

Use Chrome, Edge, Brave or Arc. Safari and Firefox can't save into a folder.

1. Open the site's game page, and log in if it needs one.
2. Press **Cmd + Option + I** and open the **Console** tab.
3. Paste the whole of [`browser-download-assets.js`](browser-download-assets.js)
   and press Enter. If Chrome blocks the paste, type `allow pasting` first. To
   reuse it, save it once under **Sources → Snippets**.
4. In the panel that appears, choose which furni and what to save, then press
   **Choose folder and start** and pick a folder.

## Choosing furni

- **All furni** - everything in the site's furni list.
- **Furni lines I pick** - every furni in the lines you tick. Lines come from
  each furni's `furniline` in the site's furni list.
- **What I record from the shop** - open a section of the game's shop and press
  **Auto-browse**: it opens every page under it, about one a second, and
  records each furni shown. Or press **Start recording** and click the pages
  yourself.

The name box narrows any of these, for example `rare_, chair`.

## What lands in the folder

```
furniture/<name>.nitro           the furni files
icons/<name>_icon.png            their icons
sprites/<name>/<sprite>.png      every sprite, plus the whole sheet
badges/<code>.gif                badges named in the site's texts
_failed.txt                      anything still missing, and why
```

The `furniture/` and `icons/` folders match PixelRP's own layout
(`nitro/overrides/bundled/furniture/` and `nitro/overrides/dcr/hof_furni/icons/`).

## Good to know

- **Resuming:** picking the same folder again skips everything already saved,
  so a stopped or interrupted run carries on where it left off. The panel also
  remembers its choices for each site in that browser.
- **Speed:** about 90 furni a second on the script's side (tested on PixelRP's
  9,145 furni with sprites: 1 min 42 s from local files). On a real site the
  network sets the pace; expect roughly 5-15 minutes for a catalogue that size.
  The settings at the top of the script control how many files download at
  once and how Auto-browse paces itself.
- **Recording limits:** it records what the shop draws, so a bundle's furni
  (which only show when the bundle is clicked) and sold-out limited items are
  missed.
- **Logged-in sites:** files are fetched with your own session, like the game
  does, and the site's logs record them against your account.
