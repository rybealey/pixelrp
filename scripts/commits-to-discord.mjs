#!/usr/bin/env node
// Posts the commits of a beta push to the staff-only #commits channel.
//
// Called by .github/workflows/commits-discord.yml on every push to beta.
// Lists before..after oldest-first and posts one embed per commit with the
// full message, linked to the commit on GitHub.
//
// Usage:
//   WEBHOOK_URL=... node scripts/commits-to-discord.mjs \
//     --before <sha> --after <sha> [--dry-run]
//
// Exits 0 (with a notice) when there is nothing to post or no webhook is
// configured, so the workflow never fails just because rollout is partial.

import { execFileSync } from 'node:child_process';

const EMBED_COLOR = 0x5865F2; // blurple
const TITLE_MAX = 256;
const DESCRIPTION_MAX = 4000;
const COMMITS_MAX = 25;
const EMBEDS_PER_POST = 10;

const args = process.argv.slice(2);
const opt = name =>
{
    const index = args.indexOf(`--${ name }`);

    return ((index >= 0) ? args[index + 1] : null);
};
const before = opt('before');
const after = opt('after');
const dryRun = args.includes('--dry-run');

if(!before || !after)
{
    console.error('usage: --before <sha> --after <sha> [--dry-run]');
    process.exit(1);
}

const git = gitArgs => execFileSync('git', gitArgs, { encoding: 'utf8', maxBuffer: (32 * 1024 * 1024) });

const repo = (process.env.GITHUB_REPOSITORY
    ?? git([ 'remote', 'get-url', 'origin' ]).trim().replace(/^.*github\.com[/:]/, '').replace(/\.git$/, ''));

// ---------------------------------------------------------------------------
// 1. Which commits did this push add? Oldest first, so the channel reads
//    chronologically. A first push or force-push may have no usable before
//    commit — fall back to just the head commit.

let shas = [];

try
{
    if(!before.match(/^0+$/)) shas = git([ 'rev-list', '--reverse', `${ before }..${ after }` ]).split('\n').filter(Boolean);
}
catch(error)
{
    console.log(`::notice::could not list ${ before }..${ after }; posting head commit only.`);
}

if(!shas.length) shas = [ git([ 'rev-parse', after ]).trim() ];

// ---------------------------------------------------------------------------
// 2. One embed per commit, within Discord's limits.

const truncate = (text, max) => ((text.length <= max) ? text : `${ text.slice(0, (max - 1)) }…`);

const buildEmbed = sha =>
{
    const [ author, date, ...messageLines ] = git([ 'show', '-s', '--format=%an%n%aI%n%B', sha ]).split('\n');
    const message = messageLines.join('\n').trim();
    const newline = message.indexOf('\n');
    const subject = ((newline >= 0) ? message.slice(0, newline) : message);
    const body = ((newline >= 0) ? message.slice(newline + 1).trim() : '');

    return {
        title: truncate((subject || sha), TITLE_MAX),
        url: `https://github.com/${ repo }/commit/${ sha }`,
        description: truncate(body, DESCRIPTION_MAX),
        color: EMBED_COLOR,
        author: { name: author },
        footer: { text: `beta · ${ sha.slice(0, 7) }` },
        timestamp: date,
    };
};

const embeds = shas.slice(0, COMMITS_MAX).map(buildEmbed);

// a giant push (history rewrite, huge merge) links the rest instead of
// flooding the channel
if(shas.length > COMMITS_MAX)
{
    embeds.push({
        title: `… and ${ shas.length - COMMITS_MAX } more commit(s)`,
        url: `https://github.com/${ repo }/compare/${ before }...${ after }`,
        color: EMBED_COLOR,
        footer: { text: 'beta' },
    });
}

if(dryRun)
{
    console.log(JSON.stringify(embeds, null, 2));
    process.exit(0);
}

// ---------------------------------------------------------------------------
// 3. Post — up to 10 embeds per webhook call, single retry on 429.

const webhookUrl = process.env.WEBHOOK_URL;

if(!webhookUrl)
{
    console.log('::notice::WEBHOOK_URL not configured for #commits; skipping post.');
    process.exit(0);
}

const post = async batch =>
{
    for(let attempt = 0; attempt < 2; attempt++)
    {
        const response = await fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ embeds: batch }),
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

for(let i = 0; i < embeds.length; i += EMBEDS_PER_POST) await post(embeds.slice(i, (i + EMBEDS_PER_POST)));

console.log(`posted ${ embeds.length } embed(s) to #commits.`);
