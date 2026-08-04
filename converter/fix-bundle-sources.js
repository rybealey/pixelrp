// Repairs cross-library `source` aliases in converted .nitro bundles.
//
// UPSTREAM BUG (nitro-converter, verified 2026-08): IMAGE_SOURCES in
// src/swf/GenerateSpritesheet.ts is a module-level Map that is never cleared
// between libraries. It accumulates asset-name -> symbol-name mappings from
// every SWF converted in the same process, so when a later library reuses a
// generic asset name (e.g. `h_std_fc_1_1_0`, which exists in many face
// libraries), AssetMapper rewrites that asset's `source` to a symbol name
// belonging to a DIFFERENT library. The renderer then resolves the alias
// within the bundle, finds nothing, and draws nothing — e.g. avatars render
// with an invisible nose and mouth because the standing face (`fc`) asset
// points at a symbol that isn't there.
//
// The images themselves are packed correctly under their own names, so the
// repair is simply: drop a `source` that does not resolve inside its own
// bundle, letting the asset fall back to its own (present) frame.
//
// Usage: node fix-bundle-sources.js <bundledDir>

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

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

function writeBundle(files) {
    const parts = [];
    const header = Buffer.alloc(2);
    header.writeInt16BE(files.length, 0);
    parts.push(header);
    for (const f of files) {
        const nameBuf = Buffer.from(f.name);
        const nl = Buffer.alloc(2); nl.writeInt16BE(nameBuf.length, 0);
        const dl = Buffer.alloc(4); dl.writeInt32BE(f.data.length, 0);
        parts.push(nl, nameBuf, dl, f.data);
    }
    return Buffer.concat(parts);
}

const root = process.argv[2];
if (!root || !fs.existsSync(root)) {
    console.error(`fix-bundle-sources: no such directory: ${root}`);
    process.exit(1);
}

let scanned = 0, repaired = 0, aliasesDropped = 0, unresolved = 0, skipped = 0;

const walk = dir => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) { walk(p); continue; }
        if (!entry.name.endsWith('.nitro')) continue;
        scanned++;
        try {
            const files = readBundle(fs.readFileSync(p));
            const jsonEntry = files.find(f => f.name.endsWith('.json'));
            if (!jsonEntry) continue;

            const json = JSON.parse(zlib.inflateSync(jsonEntry.data).toString('utf8'));
            const assets = json.assets || {};
            const frames = (json.spritesheet && json.spritesheet.frames) || {};
            const libName = json.name || '';

            const resolves = n => (n in assets) || (`${libName}_${n}` in frames);

            let changed = 0;
            for (const [name, asset] of Object.entries(assets)) {
                if (!asset || typeof asset.source !== 'string') continue;
                if (resolves(asset.source)) continue;      // legitimate in-bundle alias
                if (!resolves(name)) { unresolved++; continue; } // no own image either — leave alone
                delete asset.source;
                changed++;
            }

            if (changed) {
                jsonEntry.data = zlib.deflateSync(Buffer.from(JSON.stringify(json)));
                fs.writeFileSync(p, writeBundle(files));
                repaired++; aliasesDropped += changed;
            }
        } catch (e) {
            // Bundles from the official default-assets pack use a different
            // container encoding than nitro-converter output. They are not
            // affected by this bug (nothing rewrote their sources), so skip
            // them quietly rather than reporting noise on every run.
            skipped++;
        }
    }
};

walk(root);

console.log(`converter: bundle source repair — scanned ${scanned}, repaired ${repaired} bundle(s), dropped ${aliasesDropped} dangling alias(es)`);
if (unresolved) console.log(`converter:   (${unresolved} asset(s) had neither a valid source nor their own image — left untouched)`);
if (skipped) console.log(`converter:   (${skipped} bundle(s) skipped: not nitro-converter output, e.g. the default-assets pack)`);
