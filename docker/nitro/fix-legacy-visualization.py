#!/usr/bin/env python3
"""Recover the `visualizations` block nitro-converter drops from pre-2013 SWFs.

`VisualizationXML` reads its sizes out of `<visualizationData><graphics>`, the
wrapper Sulake added around 2013. Older furni — and every custom built against
that era, which is most of what the retro scene releases — put `<visualization>`
straight under `<visualizationData>`, so the converter finds nothing, maps
nothing, and writes a bundle with no `visualizations` key at all. Nothing fails
loudly: the client renders the furni with one layer and no states, which reads
as "the animation is broken" rather than as a conversion error.

So the XML is read back out of the SWF and mapped the way VisualizationMapper
would have. Size 32 is skipped, as it skips it.

Usage:
    python3 fix-legacy-visualization.py <bundle.nitro> <source.swf> [--force]

Idempotent: a bundle that already has `visualizations` is left alone unless
--force is given.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

VIS_XML = re.compile(rb'<visualizationData\b.*?</visualizationData>', re.S)


def swf_body(path):
    """The tag stream, past the 8-byte header. CWS is zlib, FWS is plain."""
    raw = open(path, 'rb').read()
    return zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw[8:]


def num(element, name, cast=int):
    value = element.get(name)
    return None if value is None else cast(value)


def map_frames(sequence):
    # Frames are keyed by position, not by their own id - two frames may share
    # an id, and the renderer plays them in document order.
    return {str(i): {'id': int(frame.get('id') or 0)}
            for i, frame in enumerate(sequence.findall('frame'))}


def map_layer(layer):
    out = {}
    for key, cast in (('frameRepeat', int), ('loopCount', int)):
        value = num(layer, key, cast)
        if value is not None:
            out[key] = value
    sequences = layer.findall('frameSequence')
    if sequences:
        out['frameSequences'] = {str(i): {'frames': map_frames(sequence)}
                                 for i, sequence in enumerate(sequences)}
    return out


def map_visualization(vis):
    out = {}
    for key in ('angle', 'layerCount', 'size'):
        value = num(vis, key)
        if value is not None:
            out[key] = value

    layers = {}
    for layer in vis.findall('layers/layer'):
        entry = {}
        for key, cast in (('x', int), ('y', int), ('z', int), ('alpha', int),
                          ('ink', str), ('tag', str), ('ignoreMouse', str)):
            value = num(layer, key, cast)
            if value is not None:
                entry[key] = value
        layers[layer.get('id')] = entry
    if layers:
        out['layers'] = layers

    directions = {d.get('id'): {} for d in vis.findall('directions/direction')}
    if directions:
        out['directions'] = directions

    animations = {}
    for animation in vis.findall('animations/animation'):
        entry = {}
        layer_map = {layer.get('id'): map_layer(layer)
                     for layer in animation.findall('animationLayer')}
        if layer_map:
            entry['layers'] = layer_map
        animations[animation.get('id')] = entry
    if animations:
        out['animations'] = animations

    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    force = '--force' in sys.argv
    if len(args) != 2:
        sys.exit(__doc__)
    bundle_path, swf_path = args

    entries = fb.bundle_entries(bundle_path)
    json_name = next(k for k in entries if k.endswith('.json'))
    data = json.loads(fb.inflate(entries[json_name]))
    if data.get('visualizations') and not force:
        print('%s already has visualizations - nothing to do' % bundle_path)
        return

    match = VIS_XML.search(swf_body(swf_path))
    if not match:
        sys.exit('%s carries no visualizationData XML' % swf_path)
    root = ET.fromstring(match.group().decode('latin-1'))
    if root.find('graphics') is not None:
        sys.exit('%s is not legacy - it has <graphics>, so the converter '
                 'already read it' % swf_path)

    data['visualizations'] = [map_visualization(v) for v in root.findall('visualization')
                              if num(v, 'size') != 32]
    entries[json_name] = zlib.compress(json.dumps(data).encode('utf-8'), 9)
    fb.write_bundle(bundle_path, entries)
    print('%s: wrote %d visualizations (sizes %s)' % (
        bundle_path, len(data['visualizations']),
        ', '.join(str(v.get('size')) for v in data['visualizations'])))


if __name__ == '__main__':
    main()
