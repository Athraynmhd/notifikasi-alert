import os, subprocess, collections, time
import numpy as np
from PIL import Image
import captcha_utils as cu
import datadir

TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
ALL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

N = 40
cnt = collections.Counter()
lens = collections.Counter()
samples = []
for i in range(N):
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    strong, _ = cu.strength(a)
    im = Image.fromarray((strong * 255).astype(np.uint8))
    w, h = im.size
    im = im.resize((w * 4, h * 4), Image.LANCZOS)
    fp = os.path.join(datadir.TMP, f'st_{i}.png')
    im.save(fp)
    subprocess.run([TESS, fp, fp[:-4], '--psm', '8', '-c', f'tessedit_char_whitelist={ALL}'],
                   capture_output=True)
    with open(fp[:-4] + '.txt') as f:
        t = ''.join(c for c in f.read() if c in ALL)
    lens[len(t)] += 1
    if len(t) == 5:
        samples.append(t)
        for c in t:
            cnt[c] += 1
    time.sleep(0.3)

print('reads len distribution:', dict(lens))
print('total 5-char samples:', len(samples))
print('char frequency (tesseract-as-read):')
for c, n in cnt.most_common():
    print(f'  {c}: {n}')
letters = sorted(set(cnt) - set('0123456789'))
print('LETTERS seen:', letters)
print('sample strings:')
print('  ' + '\n  '.join(samples[:30]))