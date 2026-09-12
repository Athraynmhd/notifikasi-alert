import os, sys
import numpy as np
from PIL import Image
from font_solver import FontSolver

OUT = r'C:\Users\Lenovo\AppData\Local\Temp\opencode\glyphs'
fs = FontSolver()

files = sorted(f for f in os.listdir(OUT) if f.endswith('.png'))
for name in files:
    im = np.array(Image.open(os.path.join(OUT, name)).convert('L'))
    g = (im > 128).astype(np.uint8)
    rank = fs.recognize(g, topk=4)
    preds = ' '.join(f'{c}:{s:.2f}' for c, s in rank)
    print(f'{name}: {preds}')