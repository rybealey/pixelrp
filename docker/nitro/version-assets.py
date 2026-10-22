#!/usr/bin/env python3
"""Give the gamedata and the avatar bundles addresses that change exactly when
their content does, so a browser can keep them until then.

Far from the server every file the browser has to ask about costs a round
trip. The gamedata (FurnitureData, the texts, FigureData...) was served
no-cache - asked about on every load - and every clothing bundle shared one
?v= (the figure overrides' tree hash), so a change to any one bundle sent
every player for every bundle again.

  1. FigureMap.json: each library's revision is a hash of its bundle, and
     EffectMap.json's the same for each effect lib. avatar.asset.url and
     avatar.asset.effect.url end in ?v=%revision%, which the renderer fills
     in per library - only a changed bundle gets a new address.
  2. Each gamedata URL in renderer-config.json (furnidata.url, the texts...)
     ends in ?v=<hash of the file>. nginx keeps a versioned gamedata address
     for a year (docker/web/nginx.conf, $gamedata_cache_control); the config
     itself is still revalidated on every load, so a new version is picked
     up at once.

Run on the server from the checkout, after apply-gamedata-fragments.py (which
changes the files hashed here) - and again after hand-patching a gamedata
file, or browsers keep the copy they have. renderer-config.json is VPS-only:
only the values named here are rewritten, in place, and the rest of the file
is left byte for byte. A re-run with nothing changed writes nothing.

Usage: version-assets.py <renderer-config.json>
"""
import hashlib
import json
import os
import re
import sys

ASSET_DIR = 'nitro/assets'
GAMEDATA_DIR = os.path.join(ASSET_DIR, 'gamedata')

# (config key, map file, list in it, the field naming the bundle, bundle folder)
BUNDLE_MAPS = [
    ('avatar.asset.url', 'FigureMap.json', 'libraries', 'id', 'bundled/figure'),
    ('avatar.asset.effect.url', 'EffectMap.json', 'effects', 'lib', 'bundled/effect'),
]

GAMEDATA_KEYS = [
    'furnidata.url',
    'productdata.url',
    'avatar.actions.url',
    'avatar.figuredata.url',
    'avatar.figuremap.url',
    'avatar.effectmap.url',
    'external.texts.url',
]


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def write_atomic(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(text)
    os.replace(tmp, path)


def with_version(url, version):
    if re.search(r'[?&]v=[^&]*', url):
        return re.sub(r'([?&]v=)[^&]*', lambda m: m.group(1) + version, url, count=1)
    return url + ('&' if '?' in url else '?') + 'v=' + version


def stamp_revisions(map_name, list_key, name_key, folder):
    """Each entry's revision becomes a number from its bundle's hash (48 bits,
    so it stays a whole number in JavaScript as the original 0s were)."""
    path = os.path.join(GAMEDATA_DIR, map_name)
    if not os.path.exists(path):
        print('%s: missing, left alone' % path)
        return
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    hashes = {}
    changed = missing = 0
    for entry in data.get(list_key, []):
        name = os.path.basename(str(entry.get(name_key) or ''))
        if not name:
            continue
        if name not in hashes:
            bundle = os.path.join(ASSET_DIR, folder, name + '.nitro')
            hashes[name] = int(file_hash(bundle), 16) if os.path.exists(bundle) else None
        revision = hashes[name]
        if revision is None:
            missing += 1
            continue
        if entry.get('revision') != revision:
            entry['revision'] = revision
            changed += 1
    if changed:
        write_atomic(path, json.dumps(data))
    print('%s: %d revisions changed, %d entries without a bundle' % (map_name, changed, missing))


def versioned_gamedata(url):
    name = url.split('?', 1)[0].rsplit('/', 1)[-1]
    path = os.path.join(GAMEDATA_DIR, name)
    if not name or not os.path.exists(path):
        print('  %s: no %s, left alone' % (url, path))
        return url
    return with_version(url, file_hash(path))


def main():
    config_path = sys.argv[1]

    # Revisions first: they change FigureMap and EffectMap, which are gamedata
    # hashed below.
    for _, map_name, list_key, name_key, folder in BUNDLE_MAPS:
        stamp_revisions(map_name, list_key, name_key, folder)

    if not os.path.exists(config_path):
        print('%s: missing, left alone' % config_path)
        return
    with open(config_path, encoding='utf-8') as fh:
        text = original = fh.read()

    def rewrite(key, change):
        nonlocal text
        scalar = re.search(r'("%s"\s*:\s*")([^"]*)(")' % re.escape(key), text)
        if scalar:
            text = text[:scalar.start(2)] + change(scalar.group(2)) + text[scalar.end(2):]
            return
        array = re.search(r'("%s"\s*:\s*\[)([^\]]*)(\])' % re.escape(key), text)
        if array:
            items = re.sub(r'"([^"]*)"', lambda m: '"%s"' % change(m.group(1)), array.group(2))
            text = text[:array.start(2)] + items + text[array.end(2):]
            return
        print('  %s: not in the config, left alone' % key)

    for key, *_ in BUNDLE_MAPS:
        rewrite(key, lambda url: with_version(url, '%revision%'))
    for key in GAMEDATA_KEYS:
        rewrite(key, versioned_gamedata)

    if text == original:
        print('%s: already current' % config_path)
        return
    write_atomic(config_path, text)
    print('%s: versions written' % config_path)


if __name__ == '__main__':
    main()
