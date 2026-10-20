#!/usr/bin/env python3
"""Point renderer-config's avatar.asset.url at the current figure bundles.

Browsers keep a figure bundle for a week (nginx: private, max-age=604800),
and Cloudflare never holds them, so a purge there does nothing. A fix to a
bundle that already shipped reaches a player only when the bundle's URL
changes - the ?v= on avatar.asset.url. renderer-config.json itself is served
no-cache (revalidated every load), so a new ?v= takes effect on the next load.

The beta deploy runs this with the git tree hash of
nitro/overrides/bundled/figure: it changes exactly when a bundle does.
renderer-config.json is VPS-only, so only that one value is rewritten, in
place, and the rest of the file is left byte for byte.

Usage: bump-figure-version.py <renderer-config.json> <version>
"""
import os
import re
import sys


def main():
    path, version = sys.argv[1], sys.argv[2]
    if not os.path.exists(path):
        print('%s: missing, left alone' % path)
        return
    text = open(path).read()
    m = re.search(r'("avatar\.asset\.url"\s*:\s*")([^"]*)(")', text)
    if not m:
        print('%s: no avatar.asset.url, left alone' % path)
        return
    url = m.group(2)
    if re.search(r'[?&]v=[^&]*', url):
        new = re.sub(r'([?&]v=)[^&]*', lambda v: v.group(1) + version, url, count=1)
    else:
        new = url + ('&' if '?' in url else '?') + 'v=' + version
    if new == url:
        print('avatar.asset.url already at v=%s' % version)
        return
    tmp = path + '.tmp'
    with open(tmp, 'w') as fh:
        fh.write(text[:m.start(2)] + new + text[m.end(2):])
    os.replace(tmp, path)
    print('avatar.asset.url: %s -> %s' % (url, new))


if __name__ == '__main__':
    main()
