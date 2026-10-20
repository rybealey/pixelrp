// pixelrp: per-account limits on game files (docs/asset-protection-plan.md,
// Phase 3). Everything here runs only after asset-gate.conf has checked the
// pass, so the user id and tier read here are the signed ones. Staff passes
// are never limited.
//
// THE DAILY FURNI ALLOWANCE (furniOver). An account may fetch a fixed number
// of DIFFERENT furni files a day (UTC). A file it already fetched today is
// free to fetch again, so reloads, cleared caches and a second tab cost
// nothing - only new files count. Past the allowance, new furni files answer
// 429 until midnight UTC; the ones already fetched today keep loading.
//
// Furni only. October 2026's logs: real players fetch at most ~300 different
// furni files a day, staff included, but 2,000-4,800 clothing files - the
// wardrobe pulls most of the ~3,800 clothing libraries just by being
// scrolled - so clothing can't be told apart from play this way. Furni
// (~22,900 files) is where a copy shows. 2,000 is ~7x the heaviest real day
// and puts a whole copy more than a week away for one account.
//
// The counts live in shared memory (the js_shared_dict_zone lines in
// nginx.conf) and start over whenever the web container is recreated.
//
// THE BROWSER GUARD PAUSE (paused, pollPauses). For a while after the
// client's browser guard sends a player back to the website, their account
// gets no game file at all, from any page - App\Support\AssetPause in the CMS
// decides who and until when, from rp_browser_guard_log. pollPauses asks it
// every few seconds and keeps the answer here; an answer that doesn't come
// leaves the last one standing.

const DAILY_FURNI = 2000;

// This container's own server, which lets 127.0.0.1 alone through to the CMS
// route (nginx.conf, location ~ /api/internal/).
const PAUSES_URL = 'http://127.0.0.1/api/internal/asset-pauses';

function furniOver(r) {
    const user = r.variables.cookie_prp_ap_u;

    if (!user || r.variables.cookie_prp_ap_t === 'staff') return '';

    const today = `${user}:${Math.floor(Date.now() / 86400000)}`;
    const file = `${today}:${r.uri.slice(r.uri.lastIndexOf('/') + 1)}`;
    const seen = ngx.shared.asset_furni_seen;
    const count = ngx.shared.asset_furni_count;

    if (seen.has(file)) return '';

    if ((count.get(today) || 0) >= DAILY_FURNI) return '1';

    if (seen.add(file, '1')) count.incr(today, 1);

    return '';
}

function paused(r) {
    const user = r.variables.cookie_prp_ap_u;

    if (!user || r.variables.cookie_prp_ap_t === 'staff') return '';

    const until = ngx.shared.asset_paused.get(user);

    return (until && until > (Date.now() / 1000)) ? '1' : '';
}

async function pollPauses(s) {
    let text;

    try {
        const reply = await ngx.fetch(PAUSES_URL, {
            headers: { 'X-Asset-Pass-Secret': s.variables.asset_pass_secret }
        });

        if (reply.status !== 200) {
            ngx.log(ngx.WARN, `asset pauses: the CMS answered ${reply.status}`);
            return;
        }

        text = await reply.text();
    } catch (e) {
        ngx.log(ngx.WARN, `asset pauses: ${e.message}`);
        return;
    }

    // Plain index loops: this njs (0.8) has no for...of.
    const pauses = ngx.shared.asset_paused;
    const lines = text.split('\n');
    const listed = {};

    for (let i = 0; i < lines.length; i++) {
        const parts = lines[i].trim().split(' ');

        if (parts.length !== 2 || !parts[0] || !parts[1]) continue;

        pauses.set(parts[0], Number(parts[1]));
        listed[parts[0]] = true;
    }

    const held = pauses.keys();

    for (let i = 0; i < held.length; i++) {
        if (!listed[held[i]]) pauses.delete(held[i]);
    }
}

export default { furniOver, paused, pollPauses };
