import os, subprocess, re
import numpy as np
from PIL import Image
import requests
import captcha_utils as cu
import datadir

TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
BASE = 'https://simkuliah.usk.ac.id/index.php'
inc = [0]


def ocr(img_pil, psm, wh):
    inc[0] += 1
    fp = os.path.join(datadir.TMP, f'fb_{inc[0]}.png')
    img_pil.save(fp)
    subprocess.run([TESS, fp, fp[:-4], '--psm', psm, '-c', f'tessedit_char_whitelist={wh}'],
                   capture_output=True)
    with open(fp[:-4] + '.txt') as f:
        return ''.join(c for c in f.read() if c in wh)


def big_from(a):
    strong, _ = cu.strength(a)
    im = Image.fromarray((strong * 255).astype(np.uint8))
    w, h = im.size
    return im.resize((w * 4, h * 4), Image.LANCZOS)


s = cu.new_session()
png = cu.fetch_captcha(s)
a = cu.read_rgb(png)
big = big_from(a)
gd = ocr(big, '8', '0123456789')

def submit(guess):
    r = s.post(BASE + '/login/auth',
               data={'username': '9999999999', 'password': 'x', 'captcha_answer': guess},
               allow_redirects=True, timeout=25)
    if 'Kode verifikasi' in r.text:
        return 'VERIF'
    if 'Username atau Password' in r.text:
        return 'BAD_CREDS'
    return 'OTHER'


print(f'digits guess = {gd!r} -> {submit(gd) if len(gd)==5 else "skip(len!=5)"}')
ga = ocr(big, '8', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
print(f'alnum guess (same session) = {ga!r}')
if len(ga) == 5:
    print(f'  -> {submit(ga)}   (whether VERIF means answer consumed / letter checked)')
g7 = ocr(big, '7', '0123456789')
print(f'psm7 digits guess = {g7!r} -> {submit(g7) if len(g7)==5 else "skip"}')