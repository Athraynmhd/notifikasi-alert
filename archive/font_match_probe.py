import json, os
import numpy as np
from PIL import Image
from font_solver import to_cell, iou, FontSolver, CHARSET, CANDIDATE_FONTS, FONT_DIR, render_char
import datadir

meta = json.loads(open(datadir.META, encoding='utf-8').read())
assign = json.loads(open(datadir.ASSIGN, encoding='utf-8').read())

# cluster centroids
from collections import defaultdict
group = defaultdict(list)
order = []
for m in meta:
    fn = m['file']
    cid = assign[fn]
    im = np.array(Image.open(os.path.join(datadir.GLYPHS, fn)).convert('L'))
    g = (im > 128).astype(np.uint8)
    group[cid].append(to_cell(g))
    if cid not in group['__seen'] if '__seen' in group else True:
        pass
cent = {}
for cid, cells in group.items():
    if cid == '__seen':
        continue
    avg = np.mean(cells, axis=0)
    cent[cid] = (avg > 0.5).astype(np.uint8)

# for each font, render all chars, match to every centroid
results = {f: [] for f in CANDIDATE_FONTS}
import collections
best_font = {}
for cid, c in sorted(cent.items()):
    scores = []
    for f in CANDIDATE_FONTS:
        ft = os.path.join(FONT_DIR, f)
        if not os.path.exists(ft):
            continue
        s = 0.0
        chbest = None
        for ch in CHARSET:
            try:
                r = render_char(ft, ch)
            except Exception:
                continue
            if r is None:
                continue
            sc = iou(c, to_cell(r))
            if sc > s:
                s = sc
                chbest = ch
        scores.append((s, f, chbest))
    scores.sort(reverse=True)
    top = scores[0]
    best_font[cid] = {'top_score': round(top[0], 3), 'font': top[1], 'char': top[2],
                      'second': (round(scores[1][0], 3), scores[1][1], scores[1][2]) if len(scores) > 1 else None,
                      'n': len(group[cid])}
    results.setdefault(top[1], []).append(top[0])

tot = 0
for cid, info in sorted(best_font.items()):
    tot += 1
    print(f"cluster {cid} (n={info['n']}): best={info['char']}@{info['font']} score={info['top_score']} | 2nd={info['second']}")

print()
print('top-score by font totals:')
fr = collections.Counter()
for cid, info in best_font.items():
    fr[info['font']] += 1
for f, n in fr.most_common():
    print(f'  {f}: {n} clusters best')