import sys, time, re, os, subprocess
import requests
import numpy as np
from PIL import Image
import captcha_utils as cu
import datadir

TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
BASE = 'https://simkuliah.usk.ac.id/index.php'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 25
DIG = '0123456789'
ALN = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


def ocr(img_pil, psm, wh, tag):
    fp = os.path.join(datadir.TMP, f'x_{tag}.png')
    img_pil.save(fp)
    subprocess.run([TESS, fp, fp[:-4], '--psm', psm, '-c', f'tessedit_char_whitelist={wh}'],
                   capture_output=True)
    with open(fp[:-4] + '.txt') as f:
        return ''.join(c for c in f.read() if c in wh)


def classify(r):
    txt = r.text
    if 'Kode verifikasi' in txt:
        return 'WRONG'
    if '/absensi' in r.url or '/dashboard' in r.url or '/main' in r.url:
        return 'OK'
    return 'OTHER:' + (re.search(r'<title>([^<]*)</title>', txt) or ['?'])[0]


def ascii1(mat):
    a = (np.array(mat) > 0)
    lines = []
    for y in range(a.shape[0]):
        line = ''.join('#' if a[y, x] else ' ' for x in range(a.shape[1]))
        if line.strip():
            lines.append(line.rstrip())
    return '\n'.join(lines)


stats = {'WRONG': 0, 'OK': 0, 'OTHER': 0}
won = 0
for i in range(N):
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    strong, _ = cu.strength(a)
    im = Image.fromarray((strong * 255).astype(np.uint8))
    w, h = im.size
    big = im.resize((w * 4, h * 4), Image.LANCZOS)
    gd = ocr(big, '8', DIG, 'dig')
    guess = gd if len(gd) == 5 else None
    cls = 'skip'
    if guess:
        r = s.post(BASE + '/login/auth',
                   data={'username': '9999999999', 'password': 'x', 'captcha_answer': guess},
                   allow_redirects=True, timeout=25)
        if any(x in r.url for x in ('/absensi', '/dashboard', '/main')):
            cls = 'OK'
        elif 'Kode verifikasi' in r.text:
            cls = 'WRONG'
        else:
            cls = 'OTHER'
        stats[cls] += 1
        if cls == 'OK':
            won += 1
    print(f'#{i} ocr={gd!r:8} submitted={guess!r:8} -> {cls}')
    if i < 10:
        glyphs = cu.find_char_columns(a)
        for pos, (x0, g) in enumerate(glyphs):
            print(f'   [pos {pos}]')
            print(ascii1(g))
    time.sleep(0.4)

print('-' * 55)
print('stats:', stats, '  WON:', won)