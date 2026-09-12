import os, json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

import numpy as np
from PIL import Image
from font_solver import to_cell, iou
import datadir

OUT = datadir.GLYPHS
META = datadir.META
ASSIGN = datadir.ASSIGN
DICT = datadir.DICT_JSON

# cluster id -> label (read manually from ASCII gallery of new 120-glyph set)
CLUSTER_LABELS = {
    0: '8', 1: '5', 2: '6', 3: '0', 4: '2',
    5: 'Q', 6: 'j', 7: '7', 8: '5', 9: 'Q',
    10: 'Z', 11: '2', 12: '4', 13: '7', 14: '4',
    15: '7', 16: 'S', 17: 'Z', 18: '7', 20: '5',
    21: '2', 22: '5', 23: '7', 24: '8', 25: '8',
    26: 'g', 28: 'J', 29: '4', 30: 'Z',
}

# uncertain clusters excluded (refresh on match): 19, 27, 31, 32


def main():
    meta = json.loads(open(META, encoding='utf-8').read())
    assign = json.loads(open(ASSIGN, encoding='utf-8').read())
    templates = {}  # label -> list of cells
    files_used = []
    for m in meta:
        fn = m['file']
        cid = assign.get(fn)
        if cid is None:
            continue
        label = CLUSTER_LABELS.get(cid)
        if not label:
            continue
        im = np.array(Image.open(os.path.join(OUT, fn)).convert('L'))
        g = (im > 128).astype(np.uint8)
        templates.setdefault(label, []).append(to_cell(g))
        files_used.append(fn)

    # build per-label centroid too
    cells = {}
    labels = []
    for lab, tl in templates.items():
        if not tl:
            continue
        cells[lab] = tl
        labels.append(lab)

    np.savez(DICT.replace('.json', '.npz'),
             labels=np.array(sorted(labels)),
             )
    # save templates as json
    arr = {}
    for lab in labels:
        arr[lab] = [c.astype(np.uint8).tolist() for c in cells[lab]]
    with open(DICT, 'w') as f:
        json.dump(arr, f)

    # summary
    print(f'templates classes: {len(labels)}')
    for lab in sorted(labels, key=lambda l: -len(cells[l])):
        print(f'  {lab}: {len(cells[lab])} templates')
    print(f'glyphs used: {len(files_used)}')


if __name__ == '__main__':
    main()