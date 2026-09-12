import os, sys
import numpy as np
from PIL import Image
import captcha_utils as cu

OUT = r'C:\Users\Lenovo\AppData\Local\Temp\opencode\glyphs'


def ascii1(im):
    h, w = im.shape
    lines = []
    for y in range(h):
        line = ''.join('#' if im[y, x] else ' ' for x in range(w))
        if line.strip():
            lines.append(line.rstrip())
    return '\n'.join(lines)


files = sorted(f for f in os.listdir(OUT) if f.endswith('.png'))
show = sys.argv[1:] if len(sys.argv) > 1 else [f.split('.')[0] for f in files]
for name in show:
    fname = name + '.png' if not name.endswith('.png') else name
    p = os.path.join(OUT, fname)
    if not os.path.exists(p):
        continue
    im = np.array(Image.open(p).convert('L'))
    print('=' * 40)
    print(fname)
    print(ascii1((im > 128).astype(int)))