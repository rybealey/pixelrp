/*
 * Nitro asset downloader
 *
 * Saves a Nitro hotel's furni files (.nitro), furni icons, the sprites packed
 * inside each .nitro, and badges into a folder on your computer. It runs in the
 * browser, on the site's game page, and finds every file the same way the game
 * does: from the site's own settings (renderer-config.json, ui-config.json) and
 * its furni list (FurnitureData.json).
 *
 * Use it in Chrome, Edge, Brave or Arc - Safari and Firefox can't save into a
 * folder.
 *   1. Open the site's game page (log in first if the site needs it).
 *   2. F12 (Cmd+Option+I on a Mac), then the Console tab. Paste this whole
 *      file and press Enter. If Chrome blocks the paste, type "allow pasting"
 *      first. To keep it handy, save it once under Sources > Snippets and run
 *      it from there.
 *   3. In the panel that appears, choose which furni:
 *        All furni
 *        Furni lines I pick - every furni in the lines you tick (each furni's
 *          "furniline" in the site's furni list)
 *        What I record from the shop - open a section of the game's shop and
 *          press Auto-browse: it opens every page under that section (or the
 *          whole tab, if no section is open) about once a second and adds each
 *          furni shown. Or press Start recording and click the pages yourself.
 *      then what to save, narrow it by name if you like, press "Choose folder
 *      and start" and pick a folder. Drag the panel by its title to move it.
 *
 * What lands in the folder:
 *   furniture/<name>.nitro            the furni files
 *   icons/<name>_icon.png             the shop and inventory icons
 *   sprites/<name>/<sprite>.png       every sprite cut out of the furni's sheet,
 *   sprites/<name>/_spritesheet.png   and the whole sheet
 *   badges/<code>.gif                 every badge named in the site's texts
 *   catalogue/<icon>.png              the shop's tab and page icons      } from
 *   _shop.json, _shop.txt             the shop's tabs, categories and    } recording
 *                                     pages, in order, with their furni  }
 *   lines/<line>/<name>.nitro, ..._icon.png  if ticked: a copy of each furni
 *                                     file and icon in a folder per furni line
 *   _FurnitureData.json               the site's furni list (names, sizes, sit/lay)
 *   _failed.txt                       anything still missing, and why
 * Names that differ only in capital letters get "~2" on the second, as Mac and
 * Windows folders treat them as the same file.
 *
 * Picking the same folder again skips what is already there, so a stopped or
 * interrupted run carries on where it left off; the shop pages already in its
 * _shop.json are kept, so a shop can be recorded one tab at a time. The panel
 * also remembers its choices for each site in this browser - the mode, picked
 * lines, recorded shop items and pages, ticks and name filter - so a reload or
 * a fresh paste keeps them.
 *
 * Recording sees what the shop draws: a bundle's furni (which have no icon of
 * their own on the page) are not picked up.
 */
(() =>
{
    'use strict';

    const SETTINGS = {
        concurrency: 6, // files fetched at once - lower it to go easier on the site
        retries: 3, // extra tries when the site is busy (429) or failing (5xx)
        timeout: 30000, // a download that has received nothing for this long (ms) is given up and tried again
        deadAfter: 12, // after this many files in a row from one address get no answer at all, the rest from it are skipped
        browseDelay: 1000, // Auto-browse: at least this long (ms) on each shop page - about a person's pace
        pageWait: 5000 // Auto-browse: how much longer (ms) to wait for a slow shop page before moving on
    };

    const HOST_ID = 'nitro-asset-downloader';

    if(document.getElementById(HOST_ID))
    {
        alert('The Nitro asset downloader is already open on this page.');

        return;
    }

    // ------------------------------------------------------------ fetching

    const sleep = (ms, signal = null) => new Promise(resolve =>
    {
        if(signal?.aborted) return resolve();

        let timer = null;

        const finish = () =>
        {
            clearTimeout(timer);
            signal?.removeEventListener('abort', finish);
            resolve();
        };

        timer = setTimeout(finish, ms);
        signal?.addEventListener('abort', finish, { once: true });
    });

    // Fetches a whole file. It gives up only when nothing has arrived for
    // SETTINGS.timeout, so a big file on a slow line carries on as long as it
    // keeps moving, while a site that accepts a request and never answers
    // can't hold a download slot for minutes. `stop` cancels it at once.
    const fetchBytes = async (address, stop = null) =>
    {
        const attempt = new AbortController();
        const onStop = () => attempt.abort(stop.reason);
        let timer = null;

        const arm = () =>
        {
            clearTimeout(timer);
            timer = setTimeout(() => attempt.abort(new DOMException(`no reply in ${ SETTINGS.timeout / 1000 }s`, 'TimeoutError')), SETTINGS.timeout);
        };

        if(stop?.aborted) throw (stop.reason ?? new DOMException('Stopped', 'AbortError'));

        stop?.addEventListener('abort', onStop, { once: true });
        arm();

        try
        {
            const response = await fetch(address, { signal: attempt.signal });

            if(!response.ok)
            {
                response.body?.cancel().catch(() => {});

                return { response, bytes: null };
            }

            if(!response.body) return { response, bytes: new Uint8Array(await response.arrayBuffer()) };

            const reader = response.body.getReader();
            const chunks = [];
            let size = 0;

            for(;;)
            {
                arm();

                const { done, value } = await reader.read();

                if(done) break;

                chunks.push(value);
                size += value.byteLength;
            }

            const bytes = new Uint8Array(size);
            let at = 0;

            for(const chunk of chunks)
            {
                bytes.set(chunk, at);
                at += chunk.byteLength;
            }

            return { response, bytes };
        }
        finally
        {
            clearTimeout(timer);
            stop?.removeEventListener('abort', onStop);
        }
    };

    const readJson = async address =>
    {
        let result;

        try
        {
            result = await fetchBytes(address);
        }
        catch(error)
        {
            throw new Error(`Couldn't read ${ address } (${ error?.message ?? error }).`);
        }

        if(!result.response.ok) throw new Error(`Couldn't read ${ address } (HTTP ${ result.response.status }).`);

        return JSON.parse(new TextDecoder().decode(result.bytes));
    };

    // ------------------------------------------------------------ settings

    // The game page declares `const NitroConfig = { "config.urls": [...] }` in a
    // plain script: not on `window`, but code run from the console sees it by
    // name. A game inside an iframe is reached through the frame - by eval, or
    // when the page forbids eval, by reading the frame's HTML.
    const NITRO_CONFIG = 'typeof NitroConfig !== "undefined" ? NitroConfig : undefined';

    const configUrlsFromHtml = async href =>
    {
        try
        {
            const { response, bytes } = await fetchBytes(href);

            if(!response.ok) return null;

            const match = /["']config\.urls["']\s*:\s*\[([^\]]*)\]/.exec(new TextDecoder().decode(bytes));

            return (match ? [ ...match[1].matchAll(/["']([^"']+)["']/g) ].map(entry => entry[1]) : null);
        }
        catch
        {
            return null;
        }
    };

    const findNitroConfig = async () =>
    {
        if(typeof NitroConfig !== 'undefined') return { config: NitroConfig, base: location.href, view: window };

        for(let i = 0; i < window.frames.length; i++)
        {
            const frame = window.frames[i];
            let href = null;

            try { href = frame.location.href; }
            catch { continue; } // another site's frame

            try
            {
                const config = frame.eval(NITRO_CONFIG);

                if(config) return { config, base: href, view: frame };
            }
            catch {} // eval not allowed there

            const urls = await configUrlsFromHtml(href);

            if(urls) return { config: { 'config.urls': urls }, base: href, view: frame };
        }

        return null;
    };

    const loadSettings = async () =>
    {
        let found = await findNitroConfig();

        if(!found)
        {
            const answer = prompt('Couldn\'t find the game\'s settings on this page. Run this on the page with the game open, or paste the address of the site\'s renderer-config.json here (add ui-config.json after a space if it has one):');

            if(!answer?.trim()) throw new Error('No settings address was given.');

            found = { config: { 'config.urls': answer.trim().split(/\s+/) }, base: location.href, view: window };
        }

        // Like the game: the first file to define a key keeps it. The files
        // download together and are merged in their listed order.
        const values = { ...found.config };
        const files = await Promise.all([].concat(found.config['config.urls'] ?? []).map(url => readJson(new URL(url, found.base).href)));

        for(const json of files) for(const [ key, value ] of Object.entries(json)) if(!(key in values)) values[key] = value;

        const interpolate = (text, depth = 0) => text.replace(/\${(.*?)}/g, (piece, key) =>
        {
            const value = values[key];

            return (((typeof value === 'string') && (depth < 10)) ? interpolate(value, depth + 1) : piece);
        });

        const get = key =>
        {
            const value = values[key];

            if(typeof value === 'string') return interpolate(value);

            if(Array.isArray(value)) return value.filter(entry => (typeof entry === 'string')).map(entry => interpolate(entry));

            return null;
        };

        return { get, base: found.base, view: found.view };
    };

    // ------------------------------------------------------------ the lists

    const safeName = name => (String(name).replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').replace(/^\.+$/, '_') || '_');

    // A furni line as a folder name - Windows won't make one that ends in a
    // dot or a space.
    const lineFolder = line => (safeName(line).replace(/[. ]+$/, '') || '_');

    const lastSegment = address =>
    {
        const last = new URL(address).pathname.split('/').pop();

        try { return decodeURIComponent(last); }
        catch { return last; }
    };

    const extensionOf = (address, fallback) =>
    {
        const match = /\.([a-z0-9]{2,5})$/i.exec(new URL(address).pathname);

        return (match ? `.${ match[1].toLowerCase() }` : fallback);
    };

    const escapeRegex = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    // Two wall items the game renames (RoomContentLoader.processFurnitureData).
    const WALL_RENAMES = { 'post.it': 'post_it', 'post.it.vd': 'post_it_vd' };

    // The game draws a poster's icon as "poster" plus that poster's own number
    // (RoomContentLoader.getFurnitureWallNameForTypeId), which no furni list
    // names: those icons are learned from the shop as recording sees them.
    const POSTER = 'poster';

    const loadCatalog = async settings =>
    {
        const toUrl = text => new URL(text, settings.base).href;
        const furnidataUrl = settings.get('furnidata.url');
        const furniTemplate = settings.get('furni.asset.url');
        const iconTemplate = settings.get('furni.asset.icon.url');
        const badgeTemplate = settings.get('badge.asset.url');
        const warnings = [];

        if(!furnidataUrl) throw new Error('The site\'s settings have no furnidata.url.');

        // Badges have no list of their own; the texts name each one
        // (badge_name_<code>, badge_desc_<code>). A texts file that won't load
        // is reported, and the badges named only there are left out.
        const textsUrls = (badgeTemplate ? [].concat(settings.get('external.texts.url') ?? []) : []);
        const [ furnidata, ...texts ] = await Promise.all([
            readJson(toUrl(furnidataUrl)),
            ...textsUrls.map(textsUrl => readJson(toUrl(textsUrl)).catch(error =>
            {
                warnings.push(`${ error.message } Badges named only there are missing.`);

                return {};
            }))
        ]);

        // Saved paths are compared ignoring capitals, as Mac and Windows
        // folders do: a second name differing only in capitals gets "~2".
        const usedPaths = new Set();

        const claim = (folder, stem, extension) =>
        {
            let candidate = stem;

            for(let n = 2; usedPaths.has(`${ folder }/${ candidate }${ extension }`.toLowerCase()); n++) candidate = `${ stem }~${ n }`;

            usedPaths.add(`${ folder }/${ candidate }${ extension }`.toLowerCase());

            return `${ folder }/${ candidate }${ extension }`;
        };

        const furni = new Map();
        const icons = new Map();
        const lines = new Map(); // line -> the furni in it
        const libraryOf = new Map(); // class name -> its library

        const addType = (type, wall) =>
        {
            const className = String(type?.classname ?? '').trim();

            if(!className) return;

            // "name*3" is colour 3 of library "name". A floor item's colour has
            // its own icon (name_3_icon.png); the game never gives a wall
            // item's colour one.
            let [ name, param = '' ] = className.split('*');

            if(wall)
            {
                name = (WALL_RENAMES[name] ?? name);
                param = '';
            }

            const line = (String(type?.furniline ?? '').trim() || '(no line)');

            if(!lines.has(line)) lines.set(line, new Set());

            lines.get(line).add(name);
            libraryOf.set(className, name);

            if(furniTemplate)
            {
                if(!furni.has(name))
                {
                    const path = claim('furniture', safeName(name), '.nitro');

                    furni.set(name, { kind: 'furni', name, library: name, url: toUrl(furniTemplate.replace(/%libname%/gi, name)), path, spriteDir: `sprites/${ path.slice(10, -6) }`, lines: new Set(), classNames: new Set() });
                }

                furni.get(name).lines.add(line);
                furni.get(name).classNames.add(className);
            }

            if(iconTemplate)
            {
                const url = toUrl(iconTemplate.replace(/%libname%/gi, name).replace(/%param%/gi, (param ? `_${ param }` : '')));

                if(!icons.has(url)) icons.set(url, { kind: 'icon', name: className, library: name, url, path: claim('icons', safeName(`${ name }${ param ? `_${ param }` : '' }_icon`), extensionOf(url, '.png')), lines: new Set(), classNames: new Set() });

                icons.get(url).lines.add(line);
                icons.get(url).classNames.add(className);
            }
        };

        for(const type of (furnidata?.roomitemtypes?.furnitype ?? [])) addType(type, false);
        for(const type of (furnidata?.wallitemtypes?.furnitype ?? [])) addType(type, true);

        // The shop draws each offer with its icon's address, so an address seen
        // there names its furni: matched on the address (without any ?query,
        // unless the site's icon addresses are built from one), or failing that
        // on the file name when only one icon has it.
        const queryMatters = (iconTemplate ?? '').includes('?');
        const keyOf = address => { const url = new URL(address); return (queryMatters ? url.href : (url.origin + url.pathname)); };
        const byAddress = new Map();
        const byFile = new Map();

        for(const icon of icons.values())
        {
            const file = lastSegment(icon.url);

            byAddress.set(keyOf(icon.url), icon);
            byFile.set(file, (byFile.has(file) ? null : icon)); // null: more than one icon has it
        }

        const posterPattern = ((iconTemplate && furni.has(POSTER))
            ? new RegExp(`^${ escapeRegex(keyOf(toUrl(iconTemplate.replace(/%libname%/gi, 'zzlibzz').replace(/%param%/gi, '')))).replace('zzlibzz', `(${ POSTER }.+?)`) }$`)
            : null);
        const extraIcons = new Map(); // poster icons learned from the shop, by address

        const matchIcon = (address, base) =>
        {
            let url;

            try { url = new URL(address, base).href; }
            catch { return null; }

            const known = (byAddress.get(keyOf(url)) ?? byFile.get(lastSegment(url)) ?? null);

            if(known) return known;

            const poster = posterPattern?.exec(keyOf(url));

            if(!poster) return null;

            if(!extraIcons.has(url)) extraIcons.set(url, { kind: 'icon', name: poster[1], library: POSTER, url, path: claim('icons', safeName(`${ poster[1] }_icon`), extensionOf(url, '.png')), lines: new Set(furni.get(POSTER).lines), classNames: new Set([ ...furni.get(POSTER).classNames ]) });

            return extraIcons.get(url);
        };

        const codes = new Set();

        for(const json of texts)
        {
            for(const key of Object.keys(json ?? {}))
            {
                const match = /^badge_(?:name|desc)_(.+)$/.exec(key);

                if(match) codes.add(match[1]);
            }
        }

        const badges = [ ...codes ].map(code =>
        {
            const url = toUrl(badgeTemplate.replace(/%badgename%/gi, code));

            return { kind: 'badge', name: code, url, path: claim('badges', safeName(code), extensionOf(url, '.gif')) };
        });

        return {
            furnidata,
            furni: [ ...furni.values() ],
            icons: [ ...icons.values() ],
            extraIcons,
            badges,
            lines: [ ...lines ].map(([ name, members ]) => ({ name, count: members.size })).sort((a, b) => a.name.localeCompare(b.name)),
            libraryOf,
            matchIcon,
            warnings,
            host: new URL(settings.base).host,
            view: settings.view
        };
    };

    // ------------------------------------------------------------ .nitro files

    // A .nitro is: a 16-bit file count, then per file a 16-bit name length, the
    // name, a 32-bit data length and the packed data (big-endian) - one JSON,
    // and the sprite sheet, which the game takes to be whichever file is not
    // the JSON. The data is zlib-packed, or gzip-packed by some converters
    // (it starts 1f 8b); the game reads both.
    const inflate = async bytes => new Uint8Array(await new Response(new Blob([ bytes ]).stream().pipeThrough(new DecompressionStream(((bytes[0] === 0x1f) && (bytes[1] === 0x8b)) ? 'gzip' : 'deflate'))).arrayBuffer());

    const unpackNitro = async bytes =>
    {
        const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
        const decoder = new TextDecoder();
        const files = [];
        let position = 0;
        let count = view.getInt16(position);

        position += 2;

        while(count-- > 0)
        {
            const nameLength = view.getInt16(position);

            position += 2;

            const name = decoder.decode(bytes.subarray(position, (position + nameLength)));

            position += nameLength;

            const length = view.getInt32(position);

            position += 4;

            files.push({ name, data: await inflate(bytes.subarray(position, (position + length))) });

            position += length;
        }

        return files;
    };

    // Every frame of the sheet as its own PNG, the whole sheet (as a PNG) last -
    // its being there is what marks a furni's sprites as done.
    const cutSprites = async files =>
    {
        const json = files.find(file => file.name.endsWith('.json'));
        const image = files.find(file => !file.name.endsWith('.json'));

        if(!image) throw new Error('no sprite sheet inside the .nitro');

        const isPng = image.name.toLowerCase().endsWith('.png');
        const frames = (json ? (JSON.parse(new TextDecoder().decode(json.data))?.spritesheet?.frames ?? {}) : {});
        const sheet = await createImageBitmap(new Blob([ image.data ], (isPng ? { type: 'image/png' } : {})));
        const sprites = [];
        let whole = image.data;

        try
        {
            for(const [ name, entry ] of Object.entries(frames))
            {
                const { x, y, w, h } = (entry?.frame ?? {});

                if(!(w > 0) || !(h > 0)) continue;

                const canvas = new OffscreenCanvas(w, h);
                const context = canvas.getContext('2d');

                // A packer may store a frame turned 90 degrees clockwise (its w
                // and h are still the sprite's own): turn it back.
                if(entry.rotated)
                {
                    context.translate(0, h);
                    context.rotate(-Math.PI / 2);
                    context.drawImage(sheet, x, y, h, w, 0, 0, h, w);
                }
                else
                {
                    context.drawImage(sheet, x, y, w, h, 0, 0, w, h);
                }

                sprites.push({ name: `${ safeName(name) }.png`, data: await canvas.convertToBlob({ type: 'image/png' }) });
            }

            if(!isPng)
            {
                const canvas = new OffscreenCanvas(sheet.width, sheet.height);

                canvas.getContext('2d').drawImage(sheet, 0, 0);
                whole = await canvas.convertToBlob({ type: 'image/png' });
            }
        }
        finally
        {
            sheet.close();
        }

        sprites.push({ name: '_spritesheet.png', data: whole });

        return sprites;
    };

    // ------------------------------------------------------------ the run

    class FetchFailed extends Error
    {
        constructor(status, message)
        {
            super(message);

            this.status = status;
        }
    }

    const createRun = (root, want, onChange) =>
    {
        const controller = new AbortController();
        const stats = { furni: { total: 0, saved: 0, skipped: 0, failed: 0 }, icon: { total: 0, saved: 0, skipped: 0, failed: 0 }, badge: { total: 0, saved: 0, skipped: 0, failed: 0 }, page: { total: 0, saved: 0, skipped: 0, failed: 0 } };
        const failures = [];
        const attempted = new Set();
        const dirs = new Map(); // folders made this run
        const known = new Map(); // folders found to exist
        const silent = new Map(); // address -> files in a row it gave no answer for
        const dead = new Set(); // addresses that stopped answering
        let refused = 0;

        const run = { stats, failures, dead, stopped: false, stop: () => { run.stopped = true; controller.abort(); } };

        const getDir = path =>
        {
            if(!path) return Promise.resolve(root);

            if(!dirs.has(path))
            {
                const cut = path.lastIndexOf('/');

                dirs.set(path, getDir((cut < 0) ? '' : path.slice(0, cut)).then(dir => dir.getDirectoryHandle(path.slice(cut + 1), { create: true })));
            }

            return dirs.get(path);
        };

        // Looks a folder up without making it, remembering the ones found.
        const findDir = async path =>
        {
            if(!path) return root;

            if(dirs.has(path)) return dirs.get(path);

            if(known.has(path)) return known.get(path);

            const cut = path.lastIndexOf('/');
            const dir = await (await findDir((cut < 0) ? '' : path.slice(0, cut))).getDirectoryHandle(path.slice(cut + 1));

            known.set(path, dir);

            return dir;
        };

        const existing = async path =>
        {
            try
            {
                const cut = path.lastIndexOf('/');
                const file = await (await (await findDir((cut < 0) ? '' : path.slice(0, cut))).getFileHandle(path.slice(cut + 1))).getFile();

                return ((file.size > 0) ? file : null);
            }
            catch
            {
                return null;
            }
        };

        const write = async (path, data) =>
        {
            const cut = path.lastIndexOf('/');
            const dir = await getDir((cut < 0) ? '' : path.slice(0, cut));
            const writable = await (await dir.getFileHandle(path.slice(cut + 1), { create: true })).createWritable();

            await writable.write(data);
            await writable.close();
        };

        // An address that gives no answer at all for SETTINGS.deadAfter files
        // in a row (offline, or blocking downloads from this page) is taken as
        // gone: the rest of its files fail at once instead of each spending
        // ~13s on retries.
        const download = async url =>
        {
            const origin = new URL(url).origin;

            if(dead.has(origin)) throw new FetchFailed(0, `skipped: ${ origin } stopped answering`);

            for(let attempt = 0; ; attempt++)
            {
                if(run.stopped) throw new DOMException('Stopped', 'AbortError');

                let status = 0;
                let timedOut = false;

                try
                {
                    const { response, bytes } = await fetchBytes(url, controller.signal);

                    status = response.status;
                    silent.set(origin, 0);

                    if(response.ok)
                    {
                        // A site that answers every missing file with its home page
                        if((response.headers.get('content-type') ?? '').includes('text/html')) throw new FetchFailed(404, 'not found (the site sent a web page instead)');

                        refused = 0;

                        return bytes;
                    }
                }
                catch(error)
                {
                    if(run.stopped) throw error;

                    if(error instanceof FetchFailed) throw error;

                    status = 0; // no answer, the connection dropped, or nothing arrived for SETTINGS.timeout
                    timedOut = (error?.name === 'TimeoutError');
                }

                if((status === 401) || (status === 403)) refused++;

                const retry = (((status === 0) || (status === 429) || (status >= 500)) && (attempt < SETTINGS.retries));

                if(!retry)
                {
                    if(status === 0)
                    {
                        const count = ((silent.get(origin) ?? 0) + 1);

                        silent.set(origin, count);

                        if(count >= SETTINGS.deadAfter) dead.add(origin);
                    }

                    throw new FetchFailed(status, (status ? `HTTP ${ status }` : (timedOut ? `timed out (nothing arrived for ${ SETTINGS.timeout / 1000 }s)` : 'no answer (offline, or the site blocks downloads from this page)')));
                }

                await sleep((1000 * (3 ** attempt)), controller.signal);
            }
        };

        // With "a copy in a folder per furni line" ticked, each furni file and
        // icon is also copied into lines/<line>/ for every line it is in. The
        // copy is made from the saved file, so sorting an earlier download
        // fetches nothing again.
        const lineCopies = async item =>
        {
            if(!want.lines || ((item.kind === 'furni') && !want.nitro)) return [];

            const file = item.path.slice(item.path.lastIndexOf('/') + 1);
            const copies = [];

            for(const line of want.linesOf(item))
            {
                const path = `lines/${ lineFolder(line) }/${ file }`;

                if(!(await existing(path))) copies.push(path);
            }

            return copies;
        };

        const fetchItem = async item =>
        {
            if(item.kind !== 'furni')
            {
                const local = await existing(item.path);
                const copies = await lineCopies(item);

                if(local && !copies.length) return 'skipped';

                const data = (local ?? await download(item.url));

                if(!local) await write(item.path, data);

                for(const path of copies) await write(path, data);

                return 'saved';
            }

            const local = await existing(item.path);
            const copies = await lineCopies(item);
            const needNitro = (want.nitro && !local);
            const needSprites = (want.sprites && !(await existing(`${ item.spriteDir }/_spritesheet.png`)));

            if(!needNitro && !needSprites && !copies.length) return 'skipped';

            const bytes = (local ? new Uint8Array(await local.arrayBuffer()) : await download(item.url));

            if(needNitro) await write(item.path, bytes);

            for(const path of copies) await write(path, bytes);

            if(needSprites)
            {
                let sprites;

                try
                {
                    sprites = await cutSprites(await unpackNitro(bytes));
                }
                catch(error)
                {
                    throw new Error(`${ want.nitro ? 'the .nitro is saved, but ' : '' }its sprites couldn't be cut out (${ error?.message ?? error })`);
                }

                for(const sprite of sprites) await write(`${ item.spriteDir }/${ sprite.name }`, sprite.data);
            }

            return 'saved';
        };

        // _failed.txt lists what is still missing: this run's failures, plus
        // earlier entries for files this run didn't get to. When nothing is
        // missing any more it is removed.
        const saveFailures = async () =>
        {
            const old = await existing('_failed.txt');
            const kept = (old ? (await old.text()).split('\n').slice(1).filter(row => { const address = row.split('\t')[3]; return (address && !attempted.has(address)); }) : []);
            const rows = [ ...kept, ...failures ];

            if(rows.length) await write('_failed.txt', `kind\tname\treason\taddress\n${ rows.join('\n') }\n`);
            else if(old) await root.removeEntry('_failed.txt').catch(() => {});
        };

        run.existing = existing;
        run.write = write;

        run.start = async items =>
        {
            for(const item of items) stats[item.kind].total++;

            onChange();

            let next = 0;

            const lane = async () =>
            {
                while(!run.stopped && (next < items.length))
                {
                    const item = items[next++];

                    attempted.add(item.url);

                    try
                    {
                        stats[item.kind][await fetchItem(item)]++;
                    }
                    catch(error)
                    {
                        if(run.stopped)
                        {
                            attempted.delete(item.url);

                            break;
                        }

                        stats[item.kind].failed++;
                        failures.push(`${ item.kind }\t${ item.name }\t${ error?.message ?? error }\t${ item.url }`);
                    }

                    if(refused >= 25)
                    {
                        run.stop();
                        run.refused = true;
                    }

                    onChange();
                }
            };

            await Promise.all(Array.from({ length: SETTINGS.concurrency }, lane));
            await saveFailures();
        };

        return run;
    };

    // ------------------------------------------------------------ the panel

    const host = document.createElement('div');

    host.id = HOST_ID;
    document.documentElement.appendChild(host);

    const shadow = host.attachShadow({ mode: 'open' });

    shadow.innerHTML = `
        <style>
            :host { all: initial; }
            .panel { position: fixed; top: 16px; right: 16px; z-index: 2147483647; box-sizing: border-box; width: 360px; max-width: calc(100vw - 32px);
                max-height: calc(100vh - 32px); overflow-y: auto; padding: 16px; font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                color: #ececec; background: #1c1c20; border: 1px solid #000; border-radius: 8px; box-shadow: 0 8px 28px rgba(0, 0, 0, .5); }
            .head { display: flex; align-items: center; justify-content: space-between; font-size: 14px; font-weight: 700; cursor: move; user-select: none; touch-action: none; }
            .close { all: unset; cursor: pointer; padding: 2px 6px; font-size: 18px; line-height: 1; color: #aaa; border-radius: 4px; }
            .close:hover { color: #fff; background: #2a2a30; }
            .status { margin-top: 4px; padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid #2e2e36; font-size: 12px; color: #a8a8b0; }
            .card { margin-bottom: 12px; padding: 12px; background: #232329; border: 1px solid #2e2e36; border-radius: 6px; }
            .section { margin: 0 0 8px; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: #8d8d96; }
            label { display: flex; gap: 8px; align-items: center; cursor: pointer; }
            .options { display: flex; flex-direction: column; gap: 2px; }
            .option { padding: 6px 8px; border-radius: 5px; }
            .option:hover { background: #2a2a30; }
            .option:has(input:checked) { background: #2e2e36; }
            .box { margin: 4px 0 6px 8px; padding: 10px; background: #1c1c20; border: 1px solid #2e2e36; border-radius: 5px; }
            .box[hidden] { display: none; }
            input[type=text] { box-sizing: border-box; width: 100%; padding: 7px 9px; font: inherit; color: #fff; background: #2a2a30; border: 1px solid #44444c; border-radius: 5px; }
            input[type=text]::placeholder { color: #8d8d96; }
            .line-search { margin-bottom: 8px; }
            .line-list { max-height: 160px; overflow-y: auto; padding: 4px; background: #232329; border: 1px solid #3a3a42; border-radius: 5px; color: #a8a8b0; }
            .line-list label { padding: 3px 6px; border-radius: 4px; color: #ececec; }
            .line-list label:hover { background: #2e2e36; }
            .line-list .n { margin-left: auto; color: #8d8d96; font-variant-numeric: tabular-nums; }
            .foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 8px; color: #a8a8b0; }
            .shop .foot { margin-top: 0; }
            .shop-note { margin-top: 10px; color: #c8c8d0; }
            button.link { all: unset; cursor: pointer; color: #f0954a; text-decoration: underline; }
            button.link:disabled { opacity: .45; cursor: default; }
            .saves { display: flex; flex-direction: column; gap: 8px; }
            .filter { margin-top: 12px; }
            .plan { margin: 4px 0 10px; color: #c8c8d0; }
            .buttons { display: flex; gap: 8px; }
            button.go, button.stop, button.record { flex: 1; padding: 8px 10px; font: inherit; font-weight: 700; color: #fff; border: 0; border-radius: 5px; cursor: pointer; }
            button.go { flex: 2; background: #e87332; }
            button.stop, button.record { background: #555; }
            button.record { flex: none; padding: 6px 12px; }
            button.record.on { background: #c62828; }
            button.auto { background: #e87332; }
            .shop-buttons { display: flex; gap: 8px; }
            button:disabled { opacity: .45; cursor: default; }
            .progress { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; padding: 12px; background: #232329; border: 1px solid #2e2e36; border-radius: 6px; }
            .progress:empty { display: none; }
            .progress-top { display: flex; justify-content: space-between; font-variant-numeric: tabular-nums; }
            .progress-bar { height: 4px; margin-top: 5px; background: #3a3a42; border-radius: 2px; overflow: hidden; }
            .progress-bar i { display: block; height: 100%; background: #e87332; }
            .progress-note { margin-top: 3px; font-size: 12px; color: #a8a8b0; }
            .error { margin-top: 12px; padding: 10px 12px; color: #ffb4ab; background: #3a1214; border-radius: 6px; white-space: pre-wrap; }
            .error:empty { display: none; }
        </style>
        <div class="panel">
            <div class="head" title="Drag to move"><span>Nitro asset downloader</span><button class="close" title="Close">&times;</button></div>
            <div class="status">Reading the site's settings&hellip;</div>
            <div class="card">
                <div class="section">1. Which furni</div>
                <div class="options">
                    <label class="option"><input type="radio" name="source" value="all" checked> All furni</label>
                    <label class="option"><input type="radio" name="source" value="lines"> Furni lines I pick</label>
                    <div class="box lines" hidden>
                        <input class="line-search" type="text" placeholder="Find a line&hellip;">
                        <div class="line-list"></div>
                        <div class="foot"><span class="line-count"></span><button class="link line-clear">Clear</button></div>
                    </div>
                    <label class="option"><input type="radio" name="source" value="shop"> What I record from the shop</label>
                    <div class="box shop" hidden>
                        <div class="foot"><span class="shop-buttons"><button class="record auto">Auto-browse</button><button class="record rec">Start recording</button></span><button class="link shop-clear">Clear</button></div>
                        <div class="shop-note"></div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="section">2. What to save</div>
                <div class="saves">
                    <label><input class="save" type="checkbox" name="nitro" checked> Furni files (.nitro)</label>
                    <label><input class="save" type="checkbox" name="icons" checked> Furni icons</label>
                    <label><input class="save" type="checkbox" name="sprites" checked> Sprites unpacked from each .nitro</label>
                    <label><input class="save" type="checkbox" name="badges" checked> Badges</label>
                    <label><input class="save" type="checkbox" name="layout" checked> Shop layout - the recorded categories, in order, with their icons</label>
                    <label><input class="save" type="checkbox" name="lines"> Also a copy of each furni file and icon in a folder per furni line</label>
                </div>
                <input class="filter" type="text" placeholder="Only names containing&hellip; (comma-separated)">
            </div>
            <div class="plan"></div>
            <div class="buttons"><button class="go" disabled>Choose folder and start</button><button class="stop" disabled>Stop</button></div>
            <div class="progress"></div>
            <div class="error"></div>
        </div>`;

    const $ = selector => shadow.querySelector(selector);
    const boxes = Object.fromEntries([ ...shadow.querySelectorAll('input.save') ].map(box => [ box.name, box ]));
    const number = value => value.toLocaleString();
    const plural = (value, one, many = `${ one }s`) => `${ number(value) } ${ (value === 1) ? one : many }`;
    const pickedLines = new Set();
    const recorded = new Set(); // furni class names the shop has shown while recording
    const pages = new Map(); // the shop's pages seen while recording, by pathKey: { path, furni }

    let catalog = null;
    let current = null;
    let recorder = null;
    let browser = null; // the auto-browse under way
    let browseNote = '';
    let shopOpen = false;
    let renderQueued = false;

    // Nothing works until the site's furni list has loaded.
    for(const control of shadow.querySelectorAll('input, button.link, button.record')) control.disabled = true;

    const source = () => shadow.querySelector('input[name=source]:checked').value;

    const selection = () =>
    {
        const terms = $('.filter').value.split(',').map(term => term.trim().toLowerCase()).filter(Boolean);
        const named = item => (!terms.length || terms.some(term => item.name.toLowerCase().includes(term)));
        const from = source();
        const recordedLibraries = new Set([ ...recorded ].map(className => catalog.libraryOf.get(className)).filter(Boolean));

        // A recorded furni brings every colour's icon: a shop page that groups
        // colours draws only one of them.
        const picked = item =>
        {
            if(from === 'lines') return [ ...item.lines ].some(line => pickedLines.has(line));

            if(from === 'shop') return recordedLibraries.has(item.library);

            return true;
        };
        const furni = item => (picked(item) && named(item));
        const want = { nitro: boxes.nitro.checked, icons: boxes.icons.checked, sprites: boxes.sprites.checked, badges: boxes.badges.checked, layout: (boxes.layout.checked && (pages.size > 0)), lines: (boxes.lines.checked && (boxes.nitro.checked || boxes.icons.checked)) };
        const linesFrom = ((from === 'lines') ? new Set(pickedLines) : null);

        // The line folders an item is copied into: all its lines, or only the
        // picked ones when furni are chosen by line.
        want.linesOf = item => [ ...(item.lines ?? []) ].filter(line => (!linesFrom || linesFrom.has(line)));

        return {
            want,
            items: [
                ...((want.nitro || want.sprites) ? catalog.furni.filter(furni) : []),
                ...(want.icons ? [ ...catalog.icons, ...catalog.extraIcons.values() ].filter(furni) : []),
                ...(want.badges ? catalog.badges.filter(named) : []),
                ...(want.layout ? pageIcons() : [])
            ]
        };
    };

    const showPlan = () =>
    {
        if(!catalog) return;

        const { want, items } = selection();
        const count = kind => items.filter(item => (item.kind === kind)).length;
        const layout = (want.layout ? `, and the shop's layout (${ plural(pages.size, 'page') }, ${ plural(count('page'), 'icon') })` : '');

        const sorted = (want.lines ? ` Furni files and icons are also copied into a folder per line (${ plural(new Set(items.flatMap(want.linesOf)).size, 'line') }).` : '');

        $('.plan').textContent = `Will fetch ${ plural(count('furni'), 'furni', 'furni') }, ${ plural(count('icon'), 'icon') }, ${ plural(count('badge'), 'badge') }${ layout }.${ sorted }`;
        $('.go').disabled = ((!items.length && !want.layout) || !!current || !!browser);
        queueSave();
    };

    const showSource = () =>
    {
        $('.lines').hidden = (source() !== 'lines');
        $('.shop').hidden = (source() !== 'shop');
        showPlan();
    };

    // ---- remembering the panel's choices (this browser, this site)

    // Every change to the plan is saved a moment later in the site's own
    // browser storage, and read back once the site's furni list has loaded:
    // lines and shop items the list no longer has are dropped. A browser that
    // refuses storage (a private window) just starts fresh each time.
    const SOURCES = [ 'all', 'lines', 'shop' ];
    let saveQueued = null;

    const storageKey = () => `nitro-asset-downloader:${ catalog.host }`;

    const saveChoices = () =>
    {
        clearTimeout(saveQueued);
        saveQueued = null;

        if(!catalog) return;

        try
        {
            localStorage.setItem(storageKey(), JSON.stringify({
                v: 1,
                source: source(),
                save: Object.fromEntries(Object.entries(boxes).map(([ name, box ]) => [ name, box.checked ])),
                filter: $('.filter').value,
                lines: [ ...pickedLines ],
                recorded: [ ...recorded ],
                extras: [ ...catalog.extraIcons.keys() ]
            }));
        }
        catch {}

        // A big shop's pages can outgrow the browser's storage: they are kept
        // on their own, so the rest is saved either way.
        try
        {
            localStorage.setItem(`${ storageKey() }:pages`, JSON.stringify([ ...pages.values() ]));
        }
        catch {}
    };

    const queueSave = () =>
    {
        if(!saveQueued) saveQueued = setTimeout(saveChoices, 300);
    };

    const restoreChoices = () =>
    {
        let saved = null;
        let savedPages = null;

        try { saved = JSON.parse(localStorage.getItem(storageKey()) ?? 'null'); }
        catch {}

        try { savedPages = JSON.parse(localStorage.getItem(`${ storageKey() }:pages`) ?? 'null'); }
        catch {}

        for(const page of [].concat(savedPages ?? [])) if(isPage(page)) pages.set(pathKey(page.path), page);

        if(saved?.v !== 1) return;

        const knownLines = new Set(catalog.lines.map(line => line.name));

        for(const line of [].concat(saved.lines ?? [])) if(knownLines.has(line)) pickedLines.add(line);

        for(const className of [].concat(saved.recorded ?? [])) if(catalog.libraryOf.has(className)) recorded.add(className);

        for(const address of [].concat(saved.extras ?? [])) if(typeof address === 'string') catalog.matchIcon(address);

        for(const [ name, box ] of Object.entries(boxes)) if(typeof saved.save?.[name] === 'boolean') box.checked = saved.save[name];

        if(typeof saved.filter === 'string') $('.filter').value = saved.filter;

        if(SOURCES.includes(saved.source)) shadow.querySelector(`input[name=source][value=${ saved.source }]`).checked = true;

        if(recorded.size || pages.size) browseNote = 'Kept from last time - press Clear to start over.';
    };

    addEventListener('pagehide', () => { if(saveQueued) saveChoices(); });

    // ---- furni lines

    const showLineCount = () =>
    {
        $('.line-count').textContent = (pickedLines.size ? `${ number(pickedLines.size) } picked.` : 'None picked yet.');
    };

    const renderLines = () =>
    {
        if(!catalog) return;

        const query = $('.line-search').value.trim().toLowerCase();
        const list = $('.line-list');

        list.replaceChildren();

        for(const line of catalog.lines)
        {
            if(query && !line.name.toLowerCase().includes(query)) continue;

            const label = document.createElement('label');
            const box = document.createElement('input');
            const name = document.createElement('span');
            const count = document.createElement('span');

            box.type = 'checkbox';
            box.className = 'line';
            box.checked = pickedLines.has(line.name);
            box.disabled = !!current;
            box.addEventListener('change', () =>
            {
                if(box.checked) pickedLines.add(line.name);
                else pickedLines.delete(line.name);

                showLineCount();
                showPlan();
            });

            name.textContent = line.name;
            count.className = 'n';
            count.textContent = number(line.count);
            label.append(box, name, count);
            list.append(label);
        }

        if(!list.childElementCount) list.textContent = 'No line matches.';
    };

    // ---- recording from the shop

    // Nitro's shop window (.nitro-catalog) draws each offer with its furni icon
    // as a background image. While recording, every icon address inside it is
    // matched back to its furni; icons anywhere else (inventory, room info,
    // trades) are left alone.
    const SHOP = '.nitro-catalog';

    // The shop's page list is a tree of .nitro-catalog-navigation-section
    // blocks, each a row (.layout-grid-item) followed, when open, by its
    // sub-sections. The rows on the way down to the page on screen are marked
    // active, as is the open tab above the list.
    const SECTION = '.nitro-catalog-navigation-section';
    const TABS = '.nitro-card-tabs';
    const PICTURES = '[style*="url("], img[src]';

    const rowOf = section => ([ ...section.children ].find(child => child.classList.contains('layout-grid-item')) ?? null);
    const labelOf = section => (rowOf(section)?.textContent ?? '').trim();
    const tabLabelOf = tab => tab.textContent.trim();
    const childrenOf = section => [ ...section.children ].filter(child => (child.matches(SECTION) && rowOf(child)));
    const topSectionsOf = shop => (shop ? [ ...shop.querySelectorAll(SECTION) ].filter(section => (!section.parentElement?.closest(SECTION) && rowOf(section))) : []);

    // Rows sharing a label are told apart by their order.
    const keysOf = (elements, label = labelOf) =>
    {
        const seen = new Map();

        return elements.map(element =>
        {
            const name = label(element);
            const index = (seen.get(name) ?? 0);

            seen.set(name, (index + 1));

            return { label: name, index };
        });
    };

    const addressesOf = element => ((element.tagName === 'IMG')
        ? [ element.getAttribute('src') ]
        : [ ...element.style.backgroundImage.matchAll(/url\((['"]?)(.*?)\1\)/g) ].map(match => match[2]));

    // A tab's or row's icon, as a full address.
    const iconOf = (element, base) =>
    {
        const picture = element?.querySelector(PICTURES);
        const address = (picture ? addressesOf(picture)[0] : null);

        if(!address || address.startsWith('data:')) return null;

        try { return new URL(address, base).href; }
        catch { return null; }
    };

    // Where the shop is: the open tab, then each open row down to the page on
    // screen - each with its name, its place among its neighbours (`at`), its
    // icon, and `n` to tell apart neighbours with the same name.
    const openPathOf = (shop, base) =>
    {
        const path = [];
        const tabs = [ ...shop.querySelectorAll(`${ TABS } .nav-item`) ];
        const tabAt = tabs.findIndex(tab => tab.classList.contains('active'));

        if(tabAt >= 0) path.push({ name: tabLabelOf(tabs[tabAt]), n: keysOf(tabs, tabLabelOf)[tabAt].index, at: tabAt, icon: iconOf(tabs[tabAt], base) });

        for(let list = topSectionsOf(shop); ;)
        {
            const at = list.findIndex(section => rowOf(section).classList.contains('active'));

            if(at < 0) break;

            path.push({ name: labelOf(list[at]), n: keysOf(list)[at].index, at, icon: iconOf(rowOf(list[at]), base) });
            list = childrenOf(list[at]);
        }

        return path;
    };

    const pathKey = path => JSON.stringify(path.map(step => [ step.name, step.n ]));

    const isPage = page => (Array.isArray(page?.path) && (page.path.length > 0) && page.path.every(step => (typeof step?.name === 'string')) && Array.isArray(page.furni));

    // The page on screen: its furni in the order shown (a poster learned from
    // the shop by its own name - the furni list calls them all "poster"), and
    // a fingerprint of its text and furni, which changes when a clicked page
    // has arrived.
    const pageOf = (shop, base) =>
    {
        const furni = new Set();

        for(const element of shop.querySelectorAll(PICTURES))
        {
            if(element.closest(`${ SECTION }, ${ TABS }`)) continue;

            for(const address of addressesOf(element))
            {
                const icon = catalog.matchIcon(address, base);

                if(icon) for(const name of (catalog.extraIcons.has(icon.url) ? [ icon.name ] : icon.classNames)) furni.add(name);
            }
        }

        const copy = shop.cloneNode(true);

        for(const part of copy.querySelectorAll(`${ SECTION }, ${ TABS }`)) part.remove();

        return { furni: [ ...furni ], signature: `${ copy.textContent }|${ [ ...furni ].join(',') }` };
    };

    // Adds a page, or the furni on it not seen there before. Says whether
    // anything was new.
    const addPage = (path, furni) =>
    {
        const key = pathKey(path);
        const page = pages.get(key);

        if(!page)
        {
            pages.set(key, { path, furni });

            return true;
        }

        const seen = new Set(page.furni);
        const fresh = furni.filter(name => !seen.has(name));

        page.path = path; // its latest place and icon
        page.furni.push(...fresh);

        return (fresh.length > 0);
    };

    const iconFileOf = address => `catalogue/${ safeName(lastSegment(address)) }`;

    // Each recorded tab's and page's icon, once.
    const pageIcons = () =>
    {
        const icons = new Map();

        for(const page of pages.values()) for(const step of page.path) if(step.icon && !icons.has(step.icon)) icons.set(step.icon, { kind: 'page', name: step.name, url: step.icon, path: iconFileOf(step.icon) });

        return [ ...icons.values() ];
    };

    const gameDocument = () =>
    {
        try { return (catalog?.view.document ?? null); }
        catch { return null; }
    };

    const showShop = () =>
    {
        const recording = !!recorder;

        $('.rec').textContent = (recording ? 'Stop recording' : 'Start recording');
        $('.rec').classList.toggle('on', recording);
        $('.rec').disabled = (!catalog || !!browser || !!current);
        $('.auto').textContent = (browser ? 'Stop auto-browse' : 'Auto-browse');
        $('.auto').classList.toggle('on', !!browser);
        $('.auto').disabled = (!catalog || !!current);

        let hint = '';

        if(browser) hint = ` Auto-browsing ${ browser.label }: ${ plural(browser.pages, 'page') } opened.`;
        else if(browseNote) hint = ` ${ browseNote }`;
        else if(recording) hint = (shopOpen ? ' Keep clicking through the shop pages you want.' : ' Open the shop in the game.');
        else if(!recorded.size) hint = ' Open a section of the game\'s shop and press Auto-browse, or press Start recording and click through the pages yourself.';

        $('.shop-note').textContent = `${ plural(recorded.size, 'shop item') } recorded${ pages.size ? ` on ${ plural(pages.size, 'page') }` : '' }.${ hint }`;
    };

    const startRecording = () =>
    {
        const doc = gameDocument();

        browseNote = '';

        if(!doc)
        {
            browseNote = 'Can\'t see into the game from here. Pick the game\'s frame in the Console\'s context menu (top left of the Console) and run the script again.';
            showShop();

            return false;
        }

        let timer = null;
        let openKey = null; // the page the shop's list has open
        let staleSignature = null; // what the shop showed when that page was clicked
        let lastSignature = null;

        const scan = () =>
        {
            clearTimeout(timer);
            timer = null;

            const shops = doc.querySelectorAll(SHOP);
            let added = 0;

            for(const shop of shops)
            {
                for(const element of shop.querySelectorAll(PICTURES))
                {
                    for(const address of addressesOf(element))
                    {
                        const icon = catalog.matchIcon(address, doc.baseURI);

                        if(!icon) continue;

                        for(const className of icon.classNames)
                        {
                            if(recorded.has(className)) continue;

                            recorded.add(className);
                            added++;
                        }
                    }
                }
            }

            // The page on screen goes under the row the list has open - once it
            // has changed since that row was clicked, so the last page, still
            // showing while the new one loads, isn't put there too.
            if(shops.length)
            {
                const path = openPathOf(shops[0], doc.baseURI);
                const key = pathKey(path);
                const page = pageOf(shops[0], doc.baseURI);

                if(key !== openKey)
                {
                    openKey = key;
                    staleSignature = lastSignature;
                }

                lastSignature = page.signature;

                if(path.length && (page.signature !== staleSignature) && addPage(path, page.furni)) added++;
            }
            else
            {
                openKey = null;
                lastSignature = null;
            }

            shopOpen = (shops.length > 0);
            showShop();

            if(added) showPlan();
        };

        const observer = new MutationObserver(() =>
        {
            if(!timer) timer = setTimeout(scan, 150);
        });

        observer.observe(doc.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: [ 'style', 'src', 'class' ] });

        recorder = {
            scan,
            stop: () =>
            {
                observer.disconnect();
                clearTimeout(timer);
                recorder = null;
                showShop();
            }
        };

        scan();

        return true;
    };

    // ---- auto-browse

    // Clicks through the shop's page list the way a person would, one page at
    // a time and at least SETTINGS.browseDelay apart, recording as it goes.
    // It starts from the section that is open, or covers the whole tab if none
    // is. The shop redraws the list after every click, so each row is found
    // again by the labels on the way down to it.
    const autoBrowse = async () =>
    {
        const doc = gameDocument();
        const shopNow = () => (doc?.querySelector(SHOP) ?? null);

        browseNote = '';

        if(!shopNow())
        {
            browseNote = (doc ? 'Open the shop in the game first, then press Auto-browse.' : 'Can\'t see into the game from here. Pick the game\'s frame in the Console\'s context menu (top left of the Console) and run the script again.');
            showShop();

            return;
        }

        const startedRecording = !recorder;

        if(startedRecording && !startRecording()) return;

        const topSections = () => topSectionsOf(shopNow());

        const find = path =>
        {
            let list = topSections();
            let section = null;

            for(const step of path)
            {
                section = (list.filter(entry => (labelOf(entry) === step.label))[step.index] ?? null);

                if(!section) return null;

                list = childrenOf(section);
            }

            return section;
        };

        // What the shop shows outside its page list - the page's text and
        // pictures. Its changing is how a clicked page is known to have arrived.
        const pageSignature = () =>
        {
            const shop = shopNow();

            if(!shop) return '';

            const copy = shop.cloneNode(true);

            for(const section of copy.querySelectorAll(SECTION)) section.remove();

            const pictures = [ ...copy.querySelectorAll(PICTURES) ].map(element => ((element.tagName === 'IMG') ? element.getAttribute('src') : element.style.backgroundImage));

            return `${ copy.textContent }|${ pictures.join('|') }`;
        };

        // After a click: at least browseDelay, then until what the page shows
        // has changed and been still for 300ms - the page has arrived. A page
        // that never changes (a folder with no page of its own, or one just like
        // the one before) is given up on after `patience()` more. Resolves
        // whether the page changed.
        const settle = (before, patience) => new Promise(resolve =>
        {
            const started = Date.now();
            let lastChange = started;
            let arrived = false;
            const observer = new MutationObserver(() => { lastChange = Date.now(); });

            observer.observe((shopNow() ?? doc.documentElement), { subtree: true, childList: true, attributes: true, characterData: true });

            const check = () =>
            {
                const now = Date.now();
                const waited = (now - started);

                if(!arrived && (pageSignature() !== before)) arrived = true;

                const still = ((now - lastChange) >= 300);
                const extra = patience();
                const done = (!shopNow() || run.stopped
                    || ((waited >= SETTINGS.browseDelay) && still && (arrived || (waited >= (SETTINGS.browseDelay + extra))))
                    || (waited >= (SETTINGS.browseDelay + extra + 4000)));

                if(!done)
                {
                    setTimeout(check, 150);

                    return;
                }

                observer.disconnect();
                resolve(arrived);
            };

            setTimeout(check, 150);
        });

        const tops = topSections();
        const topKeys = keysOf(tops);
        const openIndex = tops.findIndex(section => (rowOf(section).classList.contains('active') && childrenOf(section).length));
        const run = { label: ((openIndex >= 0) ? `"${ topKeys[openIndex].label }"` : 'this tab'), pages: 0, quiet: 0, stopped: false };

        run.stop = () =>
        {
            run.stopped = true;
            showShop();
        };

        browser = run;
        showShop();
        showPlan();

        const visit = async path =>
        {
            if(run.stopped || !shopNow()) return;

            let section = find(path);

            if(!section) return;

            // A section already open and chosen folds away when clicked (still
            // showing its page): click it for its page, then again to reopen it.
            const wasActive = rowOf(section).classList.contains('active');
            const wasOpen = (wasActive && (childrenOf(section).length > 0));

            // The page already on screen won't change when clicked again, so it
            // gets no extra wait. A section with sub-pages gets a shorter one
            // for a page of its own, which many sections don't have.
            const patience = () => ((wasActive && !wasOpen) ? 0 : ((wasOpen || (childrenOf(find(path) ?? section).length > 0)) ? 2000 : SETTINGS.pageWait));
            const before = pageSignature();

            rowOf(section).click();
            run.pages++;
            showShop();

            const arrived = await settle(before, patience);

            section = find(path);

            if(!section) return;

            if(wasOpen && !childrenOf(section).length)
            {
                rowOf(section).click();
                await settle(pageSignature(), () => 0);

                section = find(path);

                if(!section) return;
            }

            const children = keysOf(childrenOf(section));

            if(!arrived && !children.length && !wasActive) run.quiet++;

            for(const key of children)
            {
                if(run.stopped) return;

                await visit([ ...path, key ]);
            }
        };

        try
        {
            for(const key of ((openIndex >= 0) ? [ topKeys[openIndex] ] : topKeys))
            {
                if(run.stopped) break;

                await visit([ key ]);
            }
        }
        finally
        {
            recorder?.scan();

            const closed = !shopNow();
            const quiet = (run.quiet ? ` ${ plural(run.quiet, 'page') } showed nothing new (empty, or slow to load).` : '');

            browser = null;
            browseNote = (closed
                ? `Auto-browse stopped: the shop was closed after ${ plural(run.pages, 'page') }.`
                : (run.stopped ? `Auto-browse stopped after ${ plural(run.pages, 'page') }.` : `Auto-browse finished: ${ plural(run.pages, 'page') } opened.`)) + quiet;

            if(startedRecording) recorder?.stop();

            showShop();
            showPlan();
        }
    };

    // ---- running

    const render = () =>
    {
        renderQueued = false;

        if(!current) return;

        const lines = [ [ 'Furni', current.stats.furni ], [ 'Icons', current.stats.icon ], [ 'Badges', current.stats.badge ], [ 'Shop icons', current.stats.page ] ]
            .filter(([ , stat ]) => stat.total)
            .map(([ label, stat ]) =>
            {
                const done = (stat.saved + stat.skipped + stat.failed);
                const extra = [ (stat.skipped ? `${ number(stat.skipped) } already there` : ''), (stat.failed ? `${ number(stat.failed) } failed` : '') ].filter(Boolean).join(', ');
                const percent = Math.round((done / stat.total) * 100);

                return `<div><div class="progress-top"><span>${ label }</span><span>${ number(done) } / ${ number(stat.total) }</span></div>`
                    + `<div class="progress-bar"><i style="width: ${ percent }%"></i></div>`
                    + (extra ? `<div class="progress-note">${ extra }</div>` : '')
                    + '</div>';
            });

        $('.progress').innerHTML = lines.join('');
    };

    const queueRender = () =>
    {
        if(renderQueued) return;

        renderQueued = true;
        setTimeout(render, 250);
    };

    const setBusy = busy =>
    {
        for(const control of shadow.querySelectorAll('input, button.link')) control.disabled = busy;

        $('.stop').disabled = !busy;
        showShop();
        showPlan();
    };

    // ---- the shop's layout

    // In order: a tab first, then down each branch, a page before its
    // sub-pages - by each step's place among its neighbours.
    const comparePaths = (a, b) =>
    {
        for(let i = 0; i < Math.min(a.length, b.length); i++)
        {
            const difference = (((a[i].at ?? 0) - (b[i].at ?? 0)) || ((a[i].n ?? 0) - (b[i].n ?? 0)) || a[i].name.localeCompare(b[i].name));

            if(difference) return difference;
        }

        return (a.length - b.length);
    };

    // _shop.json lists every recorded page in shop order: its path from the
    // tab down (each step's name, place, icon address and icon file in
    // catalogue/) and its furni in the order the page shows them. Pages
    // already in the folder's _shop.json from an earlier recording are kept,
    // so a shop can be recorded one tab at a time. _shop.txt is the same as an
    // outline to read.
    const saveLayout = async run =>
    {
        const all = new Map();
        const old = await run.existing('_shop.json');

        if(old)
        {
            try { for(const page of [].concat(JSON.parse(await old.text())?.pages ?? [])) if(isPage(page)) all.set(pathKey(page.path), page); }
            catch {}
        }

        for(const [ key, page ] of pages) all.set(key, { path: page.path.map(step => ({ ...step, file: (step.icon ? iconFileOf(step.icon) : null) })), furni: page.furni });

        const sorted = [ ...all.values() ].sort((a, b) => comparePaths(a.path, b.path));
        const outline = [];
        const written = new Set();

        // A category that was never opened itself still gets its line, from
        // the pages under it.
        for(const page of sorted)
        {
            page.path.forEach((step, depth) =>
            {
                const key = pathKey(page.path.slice(0, (depth + 1)));

                if(written.has(key)) return;

                written.add(key);
                outline.push(`${ '    '.repeat(depth) }${ step.name }${ (depth === (page.path.length - 1)) ? ` - ${ plural(page.furni.length, 'furni', 'furni') }` : '' }`);
            });
        }

        await run.write('_shop.json', JSON.stringify({ site: catalog.host, saved: new Date().toISOString(), pages: sorted }, null, 1));
        await run.write('_shop.txt', `The shop of ${ catalog.host }: ${ plural(sorted.length, 'page') }\n\n${ outline.join('\n') }\n`);
    };

    // ---- moving the panel (pointer capture keeps the drag going over the game's frame)

    $('.head').addEventListener('pointerdown', event =>
    {
        if(event.target.closest('button')) return;

        const panel = $('.panel');
        const head = event.currentTarget;
        const rect = panel.getBoundingClientRect();
        const offsetX = (event.clientX - rect.left);
        const offsetY = (event.clientY - rect.top);

        const move = moved =>
        {
            panel.style.left = `${ Math.max(0, Math.min((innerWidth - rect.width), (moved.clientX - offsetX))) }px`;
            panel.style.top = `${ Math.max(0, Math.min((innerHeight - 40), (moved.clientY - offsetY))) }px`;
            panel.style.right = 'auto';
        };

        const end = () =>
        {
            head.removeEventListener('pointermove', move);
            head.removeEventListener('pointerup', end);
            head.removeEventListener('pointercancel', end);
        };

        head.setPointerCapture(event.pointerId);
        head.addEventListener('pointermove', move);
        head.addEventListener('pointerup', end);
        head.addEventListener('pointercancel', end);
        event.preventDefault();
    });

    // ---- wiring

    // Badges belong to no furni line or shop page, so picking furni that way
    // leaves them out (tick Badges again to keep them).
    for(const radio of shadow.querySelectorAll('input[name=source]')) radio.addEventListener('change', () =>
    {
        if(source() !== 'all') boxes.badges.checked = false;

        showSource();
    });

    for(const box of Object.values(boxes)) box.addEventListener('change', showPlan);

    $('.filter').addEventListener('input', showPlan);
    $('.line-search').addEventListener('input', renderLines);

    $('.line-clear').addEventListener('click', () =>
    {
        pickedLines.clear();
        renderLines();
        showLineCount();
        showPlan();
    });

    $('.rec').addEventListener('click', () =>
    {
        if(recorder) recorder.stop();
        else startRecording();
    });

    $('.auto').addEventListener('click', () =>
    {
        if(browser) browser.stop();
        else autoBrowse();
    });

    $('.shop-clear').addEventListener('click', () =>
    {
        recorded.clear();
        pages.clear();
        browseNote = '';
        showShop();
        showPlan();
    });

    $('.close').addEventListener('click', () =>
    {
        browser?.stop();
        recorder?.stop();
        current?.stop();

        if(saveQueued) saveChoices();

        host.remove();
    });

    $('.stop').addEventListener('click', () => current?.stop());

    $('.go').addEventListener('click', async () =>
    {
        $('.error').textContent = '';

        if(typeof window.showDirectoryPicker !== 'function')
        {
            $('.error').textContent = 'This browser can\'t save into a folder. Use Chrome, Edge, Brave or Arc.';

            return;
        }

        let root;

        try
        {
            root = await window.showDirectoryPicker({ id: 'nitro-assets', mode: 'readwrite' });
        }
        catch(error)
        {
            if(error?.name !== 'AbortError') $('.error').textContent = `Couldn't open that folder: ${ error?.message ?? error }`;

            return;
        }

        const { want, items } = selection();

        current = createRun(root, want, queueRender);
        setBusy(true);
        $('.status').textContent = `Saving into "${ root.name }"\u2026`;

        try
        {
            // The site's furni list goes in every time: it has the names, sizes
            // and sit/lay settings the furni files don't.
            await current.write('_FurnitureData.json', JSON.stringify(catalog.furnidata));

            if(want.layout) await saveLayout(current);

            await current.start(items);
        }
        catch(error)
        {
            $('.error').textContent = `Stopped: ${ error?.message ?? error }`;
        }

        render();

        const failed = current.failures.length;
        const dead = (current.dead.size ? ` ${ [ ...current.dead ].map(origin => new URL(origin).host).join(', ') } stopped answering - check your connection, then pick the same folder to carry on.` : '');

        $('.status').textContent = (current.refused
            ? 'Stopped: the site is refusing downloads (HTTP 401/403). Log in, or the files may be locked.'
            : `${ current.stopped ? 'Stopped' : 'Finished' }.${ failed ? ` ${ number(failed) } couldn't be fetched - see _failed.txt.` : '' }${ dead }${ (current.stopped && !dead) ? ' Pick the same folder to carry on.' : '' }`);

        current = null;
        setBusy(false);
    });

    loadSettings()
        .then(loadCatalog)
        .then(result =>
        {
            catalog = result;
            restoreChoices();
            $('.status').textContent = `${ catalog.host }: ${ plural(catalog.furni.length, 'furni', 'furni') } in ${ plural(catalog.lines.length, 'line') }, ${ plural(catalog.icons.length, 'icon') }, ${ plural(catalog.badges.length, 'badge') }.`;
            $('.error').textContent = catalog.warnings.join('\n');
            renderLines();
            showLineCount();
            setBusy(false);
            showSource();
        })
        .catch(error =>
        {
            $('.status').textContent = 'Couldn\'t read the site\'s settings.';
            $('.error').textContent = (error?.message ?? String(error));
        });
})();
