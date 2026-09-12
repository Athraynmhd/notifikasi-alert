import os, subprocess
import numpy as np
from PIL import Image
import captcha_utils as cu
import datadir
import solver_ocr

TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
BASE = 'https://simkuliah.usk.ac.id/index.php'
WH = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
inc = [0]


def ocr(img_pil, psm, wh):
    inc[0] += 1
    fp = os.path.join(datadir.TMP, f'c_{inc[0]}.png')
    img_pil.save(fp)
    subprocess.run([TESS, fp, fp[:-4], '--psm', psm, '-c', f'tessedit_char_whitelist={wh}'],
                   capture_output=True)
    with open(fp[:-4] + '.txt') as f:
        return ''.join(c for c in f.read() if c in wh)


def submit(s, guess):
    r = s.post(BASE + '/login/auth',
               data={'username': '9999999999', 'password': 'x', 'captcha_answer': guess},
               allow_redirects=True, timeout=25)
    if 'Kode verifikasi' in r.text:
        return 'VERIF'
    if 'Username atau Password' in r.text:
        return 'BAD_CREDS'
    return 'OTHER'


def big_from(a):
    strong, _ = cu.strength(a)
    im = Image.fromarray((strong * 255).astype(np.uint8))
    w, h = im.size
    return im.resize((w * 4, h * 4), Image.LANCZOS)


n = 12
won = wrong_consumed = 0
for i in range(n):
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    gd = ocr(big_from(a), '8', '0123456789')
    if len(gd) != 5:
        continue
    r1 = submit(s, gd)
    if r1 == 'BAD_CREDS':
        won += 1
        continue
    # r1 == VERIF : wrong answer. Now try alnum guess - if answer still alive => BAD_CREDS
    ga = ocr(big_from(a), '8', WH)
    if len(ga) == 5:
        r2 = submit(s, ga)
        print(f'#{i} dig={gd!r}->{r1}  aln={ga!r}->{r2}')
        if r2 == 'BAD_CREDS':
            wrong_consumed += 1
    else:
        print(f'#{i} dig={gd!r}->{r1}  aln={ga!r}(len!=5)')

print(f'digits-first solved: {won}/{n}; rescued by alnum after wrong: {wrong_consumed}')