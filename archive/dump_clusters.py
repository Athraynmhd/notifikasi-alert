import json, os
import numpy as np
from PIL import Image
from font_solver import to_cell, render_char, CHARSET, CANDIDATE_FONTS, FONT_DIR, iou
import datadir
from collections import defaultdict

meta = json.loads(open(datadir.META, encoding='utf-8').read())
assign = json.loads(open(datadir.ASSIGN, encoding='utf-8').read())

group = defaultdict(list)
files_of = defaultdict(list)
for m in meta:
    cid = assign[m['file']]
    group[cid].append(m['file'])

def ascii1(mat):
    mat = (np.array(mat) > 0).astype(np.uint8)
    lines = []
    hi, wi = mat.shape
    for y in range(hi):
        line = ''.join('#' if mat[y, x] else ' ' for x in range(wi))
        if line.strip():
            lines.append(line.rstrip())
    return '\n'.join(lines)


def font_hint(cid_files):
    # mean cell of cluster
    cells = []
    for fn in cid_files[:6]:
        im = np.array(Image.open(os.path.join(datadir.GLYPHS, fn)).convert('L'))
        cells.append(to_cell((im > 128).astype(np.uint8)))
    c = (np.mean(cells, axis=0) > 0.5).astype(np.uint8)
    best = []
    for ch in CHARSET:
        s = 0.0
        for f in CANDIDATE_FONTS:
            ft = os.path.join(FONT_DIR, f)
            if not os.path.exists(ft):
                continue
            try:
                r = render_char(ft, ch)
            except Exception:
                continue
            if r is None:
                continue
            s = max(s, iou(c, to_cell(r)))
        best.append((s, ch))
    best.sort(reverse=True)
    return best[:3]

for cid in sorted(group):
    fs = group[cid]
    print(f'### cluster {cid} (n={len(fs)}): {fs[:5]}')
    print('    font-hint:', [(round(s,2), ch) for s,ch in font_hint(fs[:6])])
    for fn in fs[:2]:
        im = np.array(Image.open(os.path.join(datadir.GLYPHS, fn)).convert('L'))
        print(f'   [{fn}]')
        print(ascii1((im > 128).astype(np.uint8)))