// Extracts furniture catalog icons from converted .nitro bundles into the
// `dcr/hof_furni/icons/` tree the client expects.
//
// WHY: nitro-converter packs each furni's icon INTO its bundle (as
// `<class>_icon_<letter>`), but the Nitro client loads catalog icons as plain
// images from `furni.asset.icon.url` — by default the official
// images.habbo.com/dcr/hof_furni/icons/ CDN. Without this step the whole
// catalog renders as empty tiles. Extracting locally means no bulk scraping
// of Habbo's CDN and the icons always match the pack you converted.
//
// Naming (verified against nitro-renderer RoomContentLoader): the client
// requests `<class>_icon.png`, or `<class>_<colour>_icon.png` for a colour
// variant (classname `<class>*<colour>`). In the bundle those are the icon
// assets suffixed _a, _b, _c … where _a is colour 1. Colour 1 is written
// under BOTH forms, since furnidata may or may not carry an explicit `*1`.
//
// Usage: node extract-furni-icons.js <bundledDir> <iconsOutDir>

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const Jimp = require('jimp');

// The jimp bundled with nitro-converter predates the *Async helpers, so wrap
// its callback API rather than assuming a newer version is installed.
const newImage = (w, h) => new Promise((resolve, reject) =>
    new Jimp(w, h, 0x00000000, (err, img) => err ? reject(err) : resolve(img)));
const toPngBuffer = img => new Promise((resolve, reject) =>
    img.getBuffer(Jimp.MIME_PNG, (err, buf) => err ? reject(err) : resolve(buf)));

function readBundle(buf) {
    const files = [];
    let off = 0;
    const count = buf.readInt16BE(off); off += 2;
    for (let i = 0; i < count; i++) {
        const nameLen = buf.readInt16BE(off); off += 2;
        const name = buf.subarray(off, off + nameLen).toString(); off += nameLen;
        const dataLen = buf.readInt32BE(off); off += 4;
        const data = buf.subarray(off, off + dataLen); off += dataLen;
        files.push({ name, data });
    }
    return files;
}

const [, , bundledDir, outDir] = process.argv;
if (!bundledDir || !outDir) {
    console.error('usage: extract-furni-icons.js <bundledDir> <iconsOutDir>');
    process.exit(1);
}
const furniDir = path.join(bundledDir, 'furniture');
if (!fs.existsSync(furniDir)) {
    console.log('converter: no furniture bundles yet — skipping icon extraction');
    process.exit(0);
}
fs.mkdirSync(outDir, { recursive: true });

(async () => {
    const bundles = fs.readdirSync(furniDir).filter(f => f.endsWith('.nitro'));
    let written = 0, skipped = 0, noIcon = 0, failed = 0;

    for (const file of bundles) {
        const libPath = path.join(furniDir, file);
        try {
            const files = readBundle(fs.readFileSync(libPath));
            const jsonEntry = files.find(f => f.name.endsWith('.json'));
            const pngEntry = files.find(f => f.name.endsWith('.png'));
            if (!jsonEntry || !pngEntry) { noIcon++; continue; }

            const json = JSON.parse(zlib.inflateSync(jsonEntry.data).toString('utf8'));
            const libName = json.name || path.basename(file, '.nitro');
            const frames = (json.spritesheet && json.spritesheet.frames) || {};

            const iconAssets = Object.keys(json.assets || {})
                .filter(n => /_icon_[a-z]$/.test(n));
            if (!iconAssets.length) { noIcon++; continue; }

            // Work out which outputs are missing before decoding the atlas —
            // decoding every PNG for an already-complete run is slow.
            const jobs = [];
            for (const assetName of iconAssets) {
                const letter = assetName.slice(-1);
                const colour = letter.charCodeAt(0) - 96;           // a -> 1
                const targets = (colour === 1)
                    ? [`${libName}_icon.png`, `${libName}_1_icon.png`]
                    : [`${libName}_${colour}_icon.png`];
                const missing = targets.filter(t => !fs.existsSync(path.join(outDir, t)));
                if (missing.length) jobs.push({ assetName, targets: missing });
                else skipped++;
            }
            if (!jobs.length) continue;

            const atlas = await Jimp.read(zlib.inflateSync(pngEntry.data));

            for (const job of jobs) {
                // The asset may alias another asset's image via `source`.
                let frameKey = `${libName}_${job.assetName}`;
                if (!frames[frameKey]) {
                    const src = (json.assets[job.assetName] || {}).source;
                    if (src) frameKey = `${libName}_${src}`;
                }
                const f = frames[frameKey];
                if (!f) { noIcon++; continue; }

                let sprite = atlas.clone().crop(f.frame.x, f.frame.y, f.frame.w, f.frame.h);
                if (f.rotated) sprite = sprite.rotate(-90);

                // Restore the original (untrimmed) canvas so icons keep a
                // consistent size and alignment in the catalog grid.
                const sw = (f.sourceSize && f.sourceSize.w) || f.frame.w;
                const sh = (f.sourceSize && f.sourceSize.h) || f.frame.h;
                const ox = (f.spriteSourceSize && f.spriteSourceSize.x) || 0;
                const oy = (f.spriteSourceSize && f.spriteSourceSize.y) || 0;

                const out = await newImage(sw, sh);
                out.composite(sprite, ox, oy);
                const buf = await toPngBuffer(out);

                for (const t of job.targets) {
                    fs.writeFileSync(path.join(outDir, t), buf);
                    written++;
                }
            }
        } catch (e) {
            failed++;
            if (failed <= 5) console.error(`converter: icon extraction failed for ${file}: ${e.message}`);
        }
    }

    console.log(`converter: furni icons — wrote ${written}, already present ${skipped}, no icon asset ${noIcon}` + (failed ? `, failed ${failed}` : ''));
})();
