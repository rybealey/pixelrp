#!/usr/bin/env node
// Posts newly added CHANGELOG.md bullets to a Discord channel webhook.
//
// Called by .github/workflows/changelog-discord.yml on pushes to beta
// (#planned) and main (#updates). Diffs CHANGELOG.md between two commits,
// keeps only bullets with at least one added line, and posts one embed per
// release that gained bullets — so appending two bullets posts exactly those
// two, and a beta->main merge posts everything new since the last merge.
//
// Usage:
//   WEBHOOK_URL=... node scripts/changelog-to-discord.mjs \
//     --before <sha> --after <sha> --channel planned|updates [--dry-run]
//
// Exits 0 (with a notice) when there is nothing to post or no webhook is
// configured, so the workflow never fails just because rollout is partial.

import { execFileSync } from 'node:child_process';

const CHANGELOG = 'CHANGELOG.md';

const CHANNELS = {
    planned: { color: 0xF1C40F, footer: 'Live on beta now' },
    updates: { color: 0xE67E22, footer: 'Now in the hotel' },
};

const SECTION_EMOJI = {
    'Added': '✨ Added',
    'Changed': '🔁 Changed',
    'Fixed': '🛠️ Fixed',
    'Known issues': '⚠️ Known issues',
};

// Discord hard limits (with headroom on the 6000 embed total).
const FIELD_VALUE_MAX = 1024;
const EMBED_FIELDS_MAX = 25;
const EMBED_CHARS_MAX = 5800;

const args = process.argv.slice(2);
const opt = name =>
{
    const index = args.indexOf(`--${ name }`);

    return ((index >= 0) ? args[index + 1] : null);
};
const before = opt('before');
const after = opt('after');
const channelName = opt('channel');
const dryRun = args.includes('--dry-run');

if(!before || !after || !CHANNELS[channelName])
{
    console.error('usage: --before <sha> --after <sha> --channel planned|updates [--dry-run]');
    process.exit(1);
}

const git = gitArgs => execFileSync('git', gitArgs, { encoding: 'utf8', maxBuffer: (32 * 1024 * 1024) });

// ---------------------------------------------------------------------------
// 1. Which line numbers of the after-version were added by this push?

let diff = '';

try
{
    diff = git([ 'diff', '--unified=0', before, after, '--', CHANGELOG ]);
}
catch(error)
{
    // e.g. a force-push whose old tip is gone — nothing sane to diff against.
    console.log(`::notice::could not diff ${ before }..${ after } for ${ CHANGELOG }; skipping.`);
    process.exit(0);
}

const addedLines = new Set();

for(const line of diff.split('\n'))
{
    const hunk = line.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@/);

    if(!hunk) continue;

    const start = parseInt(hunk[1], 10);
    const count = ((hunk[2] === undefined) ? 1 : parseInt(hunk[2], 10));

    for(let i = 0; i < count; i++) addedLines.add(start + i);
}

if(!addedLines.size)
{
    console.log('no added lines in CHANGELOG.md; nothing to post.');
    process.exit(0);
}

// ---------------------------------------------------------------------------
// 2. Walk the after-version, grouping lines into bullets under their release
//    (## heading) and section (### heading). A bullet is a "- " line plus its
//    indented continuation lines; it is "new" if any of its lines was added.

const fileLines = git([ 'show', `${ after }:${ CHANGELOG }` ]).split('\n');

const releases = []; // { date, title, sections: [{ name, bullets: [text] }] } in file order (newest first)
let release = null;
let section = null;
let bullet = null; // { lineNumbers: [], text: [] }
let inComment = false;

const flushBullet = () =>
{
    if(bullet && release && section && bullet.lineNumbers.some(n => addedLines.has(n)))
    {
        // join wrapped lines, strip the "- " marker, collapse whitespace
        const text = bullet.text.join(' ').replace(/^-\s+/, '').replace(/\s+/g, ' ').trim();

        if(text.length) section.bullets.push(text);
    }

    bullet = null;
};

for(let i = 0; i < fileLines.length; i++)
{
    const line = fileLines[i];
    const lineNumber = (i + 1);

    // the maintainers' HTML comment block is not content
    if(inComment) { if(line.includes('-->')) inComment = false; continue; }
    if(line.trimStart().startsWith('<!--')) { inComment = !line.includes('-->'); flushBullet(); continue; }

    if(line.startsWith('## '))
    {
        flushBullet();

        const heading = line.slice(3).trim();
        const match = heading.match(/^(\S+)\s+[—-]+\s+(.*)$/);

        release = { date: (match ? match[1] : ''), title: (match ? match[2] : heading), sections: [] };
        section = null;
        releases.push(release);
        continue;
    }

    if(line.startsWith('### '))
    {
        flushBullet();

        section = (release ? { name: line.slice(4).trim(), bullets: [] } : null);

        if(section) release.sections.push(section);
        continue;
    }

    if(/^- /.test(line))
    {
        flushBullet();

        bullet = { lineNumbers: [ lineNumber ], text: [ line ] };
        continue;
    }

    if(bullet && /^\s+\S/.test(line))
    {
        bullet.lineNumbers.push(lineNumber);
        bullet.text.push(line.trim());
        continue;
    }

    flushBullet();
}

flushBullet();

// keep only releases that actually gained bullets; post oldest first so a
// multi-release merge reads chronologically in the channel
const toPost = releases
    .map(entry => ({ ...entry, sections: entry.sections.filter(s => s.bullets.length) }))
    .filter(entry => entry.sections.length)
    .reverse();

if(!toPost.length)
{
    console.log('no new bullets in CHANGELOG.md; nothing to post.');
    process.exit(0);
}

// ---------------------------------------------------------------------------
// 3. Build embeds within Discord's limits.

const channel = CHANNELS[channelName];

const buildEmbeds = entry =>
{
    const footer = { text: `${ channel.footer } - ${ entry.date }` };
    const makeEmbed = cont => ({ title: (cont ? `${ entry.title } (cont.)` : entry.title), color: channel.color, footer, fields: [] });
    const embeds = [ makeEmbed(false) ];

    const embedSize = embed => (embed.title.length + footer.text.length + embed.fields.reduce((sum, field) => (sum + field.name.length + field.value.length), 0));

    const pushField = field =>
    {
        let current = embeds[embeds.length - 1];

        if((current.fields.length >= EMBED_FIELDS_MAX) || ((embedSize(current) + field.name.length + field.value.length) > EMBED_CHARS_MAX))
        {
            current = makeEmbed(true);
            embeds.push(current);
        }

        current.fields.push(field);
    };

    for(const entrySection of entry.sections)
    {
        const label = (SECTION_EMOJI[entrySection.name] ?? entrySection.name);
        let value = '';
        let first = true;

        const flushField = () =>
        {
            if(!value) return;

            pushField({ name: (first ? label : '​'), value });
            value = '';
            first = false;
        };

        for(const text of entrySection.bullets)
        {
            // a single bullet longer than a field gets hard-truncated — a
            // changelog bullet that long is a writing problem, not a limit one
            const line = `• ${ text }`.slice(0, FIELD_VALUE_MAX);

            if(value && ((value.length + 1 + line.length) > FIELD_VALUE_MAX)) flushField();

            value = (value ? `${ value }\n${ line }` : line);
        }

        flushField();
    }

    return embeds;
};

const allEmbeds = toPost.flatMap(buildEmbeds);

if(dryRun)
{
    console.log(JSON.stringify(allEmbeds, null, 2));
    process.exit(0);
}

// ---------------------------------------------------------------------------
// 4. Post — one webhook call per embed, single retry on 429.

const webhookUrl = process.env.WEBHOOK_URL;

if(!webhookUrl)
{
    console.log(`::notice::WEBHOOK_URL not configured for ${ channelName }; skipping post.`);
    process.exit(0);
}

const post = async embed =>
{
    for(let attempt = 0; attempt < 2; attempt++)
    {
        const response = await fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ embeds: [ embed ] }),
        });

        if(response.ok) return;

        if((response.status === 429) && (attempt === 0))
        {
            const body = await response.json().catch(() => ({}));

            await new Promise(resolve => setTimeout(resolve, (((body.retry_after ?? 2) * 1000) + 250)));
            continue;
        }

        throw new Error(`Discord webhook responded ${ response.status }: ${ await response.text() }`);
    }
};

for(const embed of allEmbeds) await post(embed);

console.log(`posted ${ allEmbeds.length } embed(s) to #${ channelName }.`);
