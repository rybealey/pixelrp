// docs/superpowers/plans/tools/detect-animated-figures.mjs
// Usage: node detect-animated-figures.mjs <path-to-nitro/assets/bundled/figure> [name-substring]
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { inflateSync } from 'node:zlib';

function parseNitro(buf) {
    let off = 0;
    const count = buf.readUInt16BE(off); off += 2;
    const files = {};
    for (let i = 0; i < count; i++) {
        const nlen = buf.readUInt16BE(off); off += 2;
        const name = buf.toString('utf8', off, off + nlen); off += nlen;
        const dlen = buf.readInt32BE(off); off += 4;
        let blob = buf.subarray(off, off + dlen); off += dlen;
        try { blob = inflateSync(blob); } catch { /* leave raw */ }
        files[name] = blob;
    }
    return files;
}

const dir = process.argv[2];
const filter = process.argv[3] || '';
// asset grammar: <scale>_<action>_<parttype>_<id>_<direction>_<frame>
const RE = /^[a-z]+_([a-z]+)_([a-z]+)_(\d+)_(\d+)_(\d+)$/;
const IDLE = new Set(['std', 'sit', 'lay']);

let animated = 0, total = 0;
for (const f of readdirSync(dir)) {
    if (!f.endsWith('.nitro') || !f.includes(filter)) continue;
    total++;
    const files = parseNitro(readFileSync(join(dir, f)));
    let manifest = null;
    for (const [n, b] of Object.entries(files)) {
        if (b[0] === 0x7b) { try { manifest = JSON.parse(b.toString('utf8')); break; } catch {} }
    }
    if (!manifest?.assets) continue;
    // per (action, parttype, id, direction) max frame, restricted to idle actions
    const maxFrame = {};
    for (const key of Object.keys(manifest.assets)) {
        const m = RE.exec(key);
        if (!m) continue;
        const [, action, ptype, id, d, fr] = m;
        if (!IDLE.has(action)) continue;
        const k = `${action}|${ptype}|${id}|${d}`;
        maxFrame[k] = Math.max(maxFrame[k] ?? 0, Number(fr));
    }
    const idleAnimated = Object.values(maxFrame).some(v => v > 0);
    if (idleAnimated) { animated++; if (filter) console.log('ANIMATED', f); }
}
console.log(`idle-animated bundles: ${animated} / ${total}`);
