import os, subprocess, re, time
import numpy as np
from PIL import Image
import requests
import captcha_utils as cu
import datadir

TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
BASE = 'https://simkuliah.usk.ac.id/index.php'


def ocr(img_pil):
    fp = os.path.join(datadir.TMP, 'fx.png')
    img_pil.save(fp)
    subprocess.run([TESS, fp, fp[:-4], '--psm', '8', '-c',
                    'tessedit_char_whitelist=0123456789'], capture_output=True)
    with open(fp[:-4] + '.txt') as f:
        return ''.join(c for c in f.read() if c.isdigit())


def alerts(txt):
    out = []
    for m in re.finditer(r'<div class="([^"]*(?:alert|captcha)[^"]*)">\s*(.*?)</div>', txt, re.S):
        body = re.sub(r'<[^>]+>', ' ', m.group(2))
        body = ' '.join(body.split())
        out.append((m.group(1), body[:120]))
    return out


won = 0
n = 20
for i in range(n):
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    strong, _ = cu.strength(a)
    im = Image.fromarray((strong * 255).astype(np.uint8))
    w, h = im.size
    big = im.resize((w * 4, h * 4), Image.LANCZOS)
    guess = ocr(big)
    if len(guess) != 5:
        time.sleep(0.3)
        continue
    r = s.post(BASE + '/login/auth',
               data={'username': '9999999999', 'password': 'x', 'captcha_answer': guess},
               allow_redirects=True, timeout=25)
    al = alerts(r.text)
    has_verif = 'Kode verifikasi' in r.text
    tag = 'VERIF' if has_verif else 'OTHER'
    if not has_verif:
        won += 1
        print(f'{i:2} guess={guess} -> {tag}  alerts={al}')
    else:
        print(f'{i:2} guess={guess} -> {tag}')
    time.sleep(0.3)

print('won(no-verif):', won, '/ 5-char guesses')