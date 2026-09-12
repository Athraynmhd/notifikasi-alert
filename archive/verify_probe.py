import sys
import numpy as np
import captcha_utils as cu
from captcha_solver import GlyphSolver
from font_solver import to_cell, iou

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def ascii1(mat, th=0.5):
    a = (np.array(mat) > th)
    lines = []
    for y in range(a.shape[0]):
        line = ''.join('#' if a[y, x] else ' ' for x in range(a.shape[1]))
        if line.strip():
            lines.append(line.rstrip())
    return '\n'.join(lines)


sol = GlyphSolver()
kept = 0
while kept < N:
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    glyphs = cu.find_char_columns(a)
    if len(glyphs) != 5:
        continue
    kept += 1
    print('=' * 70)
    for pos, (x0, g) in enumerate(glyphs):
        top = sol.recognize(g)
        print(f'--- pos {pos} (col {x0}) top={top[:3]}')
        print('   ' + '   '.join(f'{ch}:{sc:.2f}' for ch, sc in top[:3]))
        print(ascii1(g))