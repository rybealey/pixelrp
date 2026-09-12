#!/usr/bin/env python3
"""Does every item on a shelf have a picture, and every shelf an icon?

The other icon scripts work from the asset tree outwards: extract-furni-icons
crops what our bundles happen to contain, fetch-variant-icons backfills the
`*N` colour variants FurnitureData registers, mirror-c-images mirrors what the
database references. All three measure coverage against the FURNI LIBRARY.

This one measures it against the CATALOG, which is the only place a missing
icon is actually visible: a shelf full of grey squares. After a catalog rebuild
(119) put ~13,400 items on ~330 new pages, "we have 98% of the library" stopped
being the useful number - what matters is whether the items now for sale have
icons, and whether the new pages' icon_image ids exist as files.

Reads the live database through docker compose, so it runs on the VPS where
the asset tree actually lives. Point it at a stack with COMPOSE:

    COMPOSE="docker compose -p pixelrp-beta -f compose.yaml -f compose.prod.yaml -f compose.beta.yaml" \\
        python3 docker/nitro/check-catalog-icons.py

Read-only by default. `--fetch` pulls what is missing from Sulake's CDN - furni
icons from dcr/hof_furni/{revision}/ the way fetch-variant-icons does, category
icons from c_images/catalogue/ - and reports what it could not find, which is
the set that needs a local answer (a synthesised icon, or a different
icon_image on the page).
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS = os.path.join(REPO, "nitro/assets/dcr/hof_furni/icons")
CATALOGUE = os.path.join(REPO, "nitro/assets/c_images/catalogue")
FD = os.path.join(REPO, "nitro/assets/gamedata/FurnitureData.json")
FURNI_CDN = "https://images.habbo.com/dcr/hof_furni"
IMAGE_CDN = "https://images.habbo.com/c_images/catalogue"

COMPOSE = shlex.split(os.environ.get("COMPOSE", "docker compose"))


def query(sql):
    """One column, one row per line, straight out of the db container."""
    cmd = COMPOSE + ["exec", "-T", "db", "sh", "-c",
                     'exec mysql -N -B -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"']
    out = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"database query failed:\n{out.stderr.strip()}")
    return [l for l in out.stdout.splitlines() if l.strip()]


def icon_name(classname):
    """What nitro-renderer asks for: base_icon.png, or base_param_icon.png for
    an indexed colour variant. Mirrors RoomContentLoader.getAssetUrls."""
    if "*" in classname:
        base, param = classname.split("*", 1)
        return f"{base}_{param}_icon.png"
    return f"{classname}_icon.png"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true",
                    help="download what is missing instead of only listing it")
    args = ap.parse_args()

    for path in (ICONS, CATALOGUE):
        os.makedirs(path, exist_ok=True)

    sold = query(
        "SELECT DISTINCT f.item_name FROM catalog_items ci "
        "JOIN furniture f ON f.id = CAST(ci.item_id AS UNSIGNED);")
    page_icons = [int(n) for n in query(
        "SELECT DISTINCT icon_image FROM catalog_pages "
        "WHERE icon_image IS NOT NULL AND icon_image > 0;")]

    have_furni = set(os.listdir(ICONS))
    have_cat = set(os.listdir(CATALOGUE))

    missing_furni = sorted({c: icon_name(c) for c in sold}.items(),
                           key=lambda kv: kv[0])
    missing_furni = [(c, n) for c, n in missing_furni if n not in have_furni]
    missing_cat = [n for n in sorted(page_icons) if f"icon_{n}.png" not in have_cat]

    print(f"items on a shelf        {len(sold):>6}")
    print(f"  without an icon       {len(missing_furni):>6}"
          f"   ({100 * (1 - len(missing_furni) / max(len(sold), 1)):.1f}% covered)")
    print(f"page icon_image values  {len(page_icons):>6}")
    print(f"  without a file        {len(missing_cat):>6}")
    if missing_cat:
        print(f"    {missing_cat}")
    if missing_furni:
        print("  sample:", ", ".join(c for c, _ in missing_furni[:10]))

    if not args.fetch or not (missing_furni or missing_cat):
        return

    # Revisions come from FurnitureData: the CDN path is per-revision, so an
    # icon cannot be fetched without knowing which build shipped it.
    revision = {}
    if os.path.exists(FD):
        d = json.load(open(FD))
        for section in ("roomitemtypes", "wallitemtypes"):
            for t in d[section]["furnitype"]:
                revision[t["classname"]] = t.get("revision")

    stats = {"furni": 0, "cat": 0, "norev": 0, "miss": 0}

    def grab(url, dest):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pixelrp-asset-repair"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
        except Exception:
            return False
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return False
        open(dest, "wb").write(data)
        return True

    def furni_job(job):
        classname, name = job
        rev = revision.get(classname)
        if rev is None:
            stats["norev"] += 1
            return
        if grab(f"{FURNI_CDN}/{rev}/{name}", os.path.join(ICONS, name)):
            stats["furni"] += 1
        else:
            stats["miss"] += 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(furni_job, missing_furni))

    for n in missing_cat:
        if grab(f"{IMAGE_CDN}/icon_{n}.png", os.path.join(CATALOGUE, f"icon_{n}.png")):
            stats["cat"] += 1

    print(f"\nfetched: {stats['furni']} furni icons, {stats['cat']} category icons")
    print(f"unfetched: {stats['miss']} not on the CDN, {stats['norev']} with no revision "
          f"in FurnitureData, {len(missing_cat) - stats['cat']} category icons")


if __name__ == "__main__":
    main()
