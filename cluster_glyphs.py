import json
import numpy as np
from PIL import Image
from font_solver import to_cell, iou
import datadir
import os

THRESH = 0.50

meta = json.loads(open(datadir.META, encoding='utf-8').read())
cells = {}
for m in meta:
    im = np.array(Image.open(os.path.join(datadir.GLYPHS, m['file'])).convert('L'))
    g = (im > 128).astype(np.uint8)
    cells[m['file']] = to_cell(g)

files = list(cells)
clusters = []
for fn in files:
    c = cells[fn]
    best_i, best_s = -1, THRESH
    for i, cl in enumerate(clusters):
        s = iou(c, cl['centroid'])
        if s > best_s:
            best_s, best_i = s, int(i)
    if best_i >= 0:
        clusters[best_i]['files'].append(fn)
        avg = np.mean([cells[f] for f in clusters[best_i]['files']], axis=0)
        clusters[best_i]['centroid'] = (avg > 0.5).astype(np.uint8)
    else:
        clusters.append({'files': [fn], 'centroid': c})

clusters.sort(key=lambda cl: -len(cl['files']))
print(f'{len(files)} glyphs -> {len(clusters)} clusters at thresh {THRESH}')

assign = {}
for i, cl in enumerate(clusters):
    for fn in cl['files']:
        assign[fn] = i
with open(datadir.ASSIGN, 'w') as f:
    f.write(json.dumps(assign))