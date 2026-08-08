#!/usr/bin/env python3
"""Rebrand game text: Habbo -> PixelRP, (a) Habbo(s)-as-players -> Pixel(s).

Rewrites string VALUES in nitro/assets/gamedata/ExternalTexts.json:
  - "a Habbo" / "A Habbo"      -> "a Pixel" / "A Pixel"
  - "Habbos" / "habbos"        -> "Pixels" / "pixels"
  - "Habbo" / "habbo" (word)   -> "PixelRP"
  - bare "habbo.com(.br)"      -> "pixelrp.co"

Deliberately preserved: URLs, email addresses, event:... link targets
(masked before replacement), and compound proper nouns such as Habboween,
HabboQuests, Habbox, FlyHabbo (word-boundary regexes never match inside
them). Keys are never touched. Idempotent — re-run after regenerating
gamedata from the converter (which restores Habbo branding):

    python3 docker/nitro/rename-habbo-to-pixelrp.py
"""
import json, os, re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(REPO, 'nitro/assets/gamedata/ExternalTexts.json')

MASK = '\x00MASK{}\x00'

def transform(v):
    masks = []
    def mask(m):
        masks.append(m.group(0))
        return MASK.format(len(masks) - 1)
    v = re.sub(r'https?://[^\"\s<>]+|[\w.+-]+@[\w.-]+\.\w+|event:[^\"\s<>]+', mask, v)
    v = re.sub(r'\b[Hh]abbo\.com(\.br)?\b', 'pixelrp.co', v)
    v = re.sub(r'\ba Habbo\b', 'a Pixel', v)
    v = re.sub(r'\bA Habbo\b', 'A Pixel', v)
    v = re.sub(r'\ban? habbo\b', 'a pixel', v)
    v = re.sub(r'\bHabbos\b', 'Pixels', v)
    v = re.sub(r'\bhabbos\b', 'pixels', v)
    v = re.sub(r'\bHabbo\b', 'PixelRP', v)
    v = re.sub(r'\bhabbo\b', 'PixelRP', v)
    for i, orig in enumerate(masks):
        v = v.replace(MASK.format(i), orig)
    return v

d = json.load(open(FILE))
changed = 0
for k in d:
    if not isinstance(d[k], str):
        continue
    new = transform(d[k])
    if new != d[k]:
        d[k] = new
        changed += 1

json.dump(d, open(FILE, 'w'), ensure_ascii=False, separators=(',', ':'))
print(f'values changed: {changed}')
