import io, os, subprocess, re
import requests
import numpy as np
from PIL import Image
import captcha_utils as cu
import datadir

TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
BASE = 'https://simkuliah.usk.ac.id/index.php'
WH = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


def ocr(img_pil):
    fp = os.path.join(datadir.TMP, 'dbg.png')
    img_pil.save(fp)
    subprocess.run([TESS, fp, fp[:-4], '--psm', '7', '-c', f'tessedit_char_whitelist={WH}'],
                   capture_output=True)
    with open(fp[:-4] + '.txt') as f:
        return ''.join(c for c in f.read() if c in WH)


def msg(r):
    m = re.search(r'(?:alert-danger|error|flash)[^>]*>\s*([^<]{2,200})', r.text, re.I)
    return (m.group(1).strip()[:100] if m else '') or re.search(r'<title>([^<]*)</title>', r.text, re.I).group(1)


s = cu.new_session()
png1 = cu.fetch_captcha(s)
a1 = cu.read_rgb(png1)
strong1, _ = cu.strength(a1)
g1 = ocr(Image.fromarray((strong1 * 255).astype(np.uint8)))
print(f'captcha img1 bytes={len(png1)} hash={hash(png1) % 10**6}')

# fetch again same session WITHOUT touching login page first
r = s.get(BASE + '/login/captcha_image?t=2', timeout=20)
png2 = r.content
a2 = cu.read_rgb(png2)
strong2, _ = cu.strength(a2)
g2 = ocr(Image.fromarray((strong2 * 255).astype(np.uint8)))
print(f'captcha img2 bytes={len(png2)} hash={hash(png2) % 10**6}  img1==img2? {png1 == png2}')
print(f'ocr img1={g1!r}  img2={g2!r}')

def post(a):
    rr = s.post(BASE + '/login/auth',
                data={'username': '9999999999', 'password': 'x', 'captcha_answer': a},
                allow_redirects=True, timeout=25)
    print(f'  POST {a!r:12} -> HTTP{r.status_code} final={rr.url[:60]} msg={msg(rr)}')

print('step1: submit wrong guess for img1')
post('ZZZZZ')
print('step2: same session, submit img2 guess:')
post(g2 if len(g2) == 5 else '00000')
print('step3: same session, replay ZZZZZ again (answer consumed?):')
post('ZZZZZ')