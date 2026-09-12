import subprocess, sys, io, os
import numpy as np
from PIL import Image
import captcha_utils as cu
import datadir

TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
TMP = datadir.TMP
_inc = [0]


def run_tess(img_pil, config):
    _inc[0] += 1
    fp = os.path.join(TMP, f'tess_{_inc[0]}.png')
    img_pil.save(fp)
    base = fp[:-4]
    subprocess.run([TESS, fp, base, '--psm', config, '-c',
                    'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'],
                   capture_output=True)
    with open(base + '.txt', 'r') as f:
        r = f.read()
    return r.strip()


def upscale(img_pil, x=3):
    w, h = img_pil.size
    return img_pil.resize((w * x, h * x), Image.LANCZOS)


N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
kept = 0
while kept < N:
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    glyphs = cu.find_char_columns(a)
    if len(glyphs) != 5:
        continue
    kept += 1
    strong, soft = cu.strength(a)
    binimg = Image.fromarray((strong * 255).astype(np.uint8))
    print('=' * 60)
    print(f'captcha #{kept}  full-image OCR (psm7): "',
          run_tess(upscale(binimg, 3), '7'), '"')
    line = []
    for pos, (x0, g) in enumerate(glyphs):
        gi = Image.fromarray((g * 255).astype(np.uint8))
        gi = upscale(gi, 4)
        r = run_tess(gi, '10')
        ch = r[0] if r else '?'
        line.append(ch)
    print(f'  per-glyph psm10: {"".join(line)}')