#!/usr/bin/env python3
"""Regenerate the emulator's figuredata.xml from the client's FigureData.json.

The Nitro client renders avatars from nitro/assets/gamedata/FigureData.json,
but PlusEMU validates every saved look against emulator/Config/figuredata.xml
(FigureDataManager.ProcessFigure). When the XML is an older/smaller revision
than the JSON, any clothing set the client offers but the server doesn't know
is SILENTLY DROPPED on save, and the emulator's `_requirements` loop
substitutes the first same-gender set of that type — e.g. a male who picks
modern denim shorts ends up in leg set 3017 (a kilt). The two files must
therefore describe the same set universe.

This converts FigureData.json into the exact XML schema
FigureDataManager.Init() parses:

    <figuredata>
      <colors>
        <palette id="1">
          <color id="14" index="0" club="0" selectable="1">F5DA88</color>
      <sets>
        <settype type="lg" paletteid="3" mand_m_0="1" mand_f_0="1" ...>
          <set id="3526" gender="U" club="0" colorable="1" selectable="1" preselectable="0">
            <part id="2908" type="lg" colorable="1" index="0" colorindex="1"/>

Run after every converter run that rewrites FigureData.json:
    python3 docker/nitro/figuredata-json-to-xml.py

Then rebuild the emulator image so Config/figuredata.xml is baked in.
"""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "nitro/assets/gamedata/FigureData.json"
DST = ROOT / "emulator/Config/figuredata.xml"

# The emulator adds hd set 99999 ("Faceless") itself after load; emitting it
# here would collide on the dictionary Add and crash startup.
EMULATOR_RESERVED = {("hd", 99999)}

MAND = [
    ("mandatory_m_0", "mand_m_0"),
    ("mandatory_f_0", "mand_f_0"),
    ("mandatory_m_1", "mand_m_1"),
    ("mandatory_f_1", "mand_f_1"),
]


def b(v):
    return "1" if v else "0"


def main():
    data = json.loads(SRC.read_text())
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<figuredata>", "<colors>"]

    for pal in data["palettes"]:
        out.append(f'<palette id="{pal["id"]}">')
        for c in pal["colors"]:
            hexcode = escape(str(c.get("hexCode", "")))
            out.append(
                f'<color id="{c["id"]}" index="{c.get("index", 0)}" '
                f'club="{c.get("club", 0)}" selectable="{b(c.get("selectable"))}">{hexcode}</color>'
            )
        out.append("</palette>")
    out.append("</colors>")

    out.append("<sets>")
    set_count = 0
    for st in data["setTypes"]:
        t = st["type"]
        attrs = f'type="{t}" paletteid="{st["paletteId"]}"'
        for jk, xk in MAND:
            if jk in st:
                attrs += f' {xk}="{b(st[jk])}"'
        out.append(f"<settype {attrs}>")
        seen_sets = set()
        for s in st["sets"]:
            sid = int(s["id"])
            if (t, sid) in EMULATOR_RESERVED or sid in seen_sets:
                continue
            seen_sets.add(sid)
            set_count += 1
            out.append(
                f'<set id="{sid}" gender="{s["gender"]}" club="{s.get("club", 0)}" '
                f'colorable="{b(s.get("colorable"))}" selectable="{b(s.get("selectable"))}" '
                f'preselectable="{b(s.get("preselectable"))}">'
            )
            seen_parts = set()
            for p in s.get("parts", []):
                pkey = (int(p["id"]), p["type"])
                if pkey in seen_parts:
                    continue
                seen_parts.add(pkey)
                out.append(
                    f'<part id="{p["id"]}" type="{p["type"]}" '
                    f'colorable="{b(p.get("colorable"))}" index="{p.get("index", 0)}" '
                    f'colorindex="{p.get("colorindex", 0)}"/>'
                )
            out.append("</set>")
        out.append("</settype>")
    out.append("</sets>")
    out.append("</figuredata>")

    DST.write_text("\n".join(out))
    print(f"wrote {DST} — {len(data['palettes'])} palettes, "
          f"{len(data['setTypes'])} settypes, {set_count} sets")


if __name__ == "__main__":
    sys.exit(main())
