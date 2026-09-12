import requests, re

BASE = 'https://simkuliah.usk.ac.id/index.php'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      'Referer': BASE + '/login'}


def probe(body, label):
    print('=' * 70)
    print(f'[{label}]')
    s = requests.Session()
    s.headers.update(UA)
    s.get(BASE + '/login')
    img = s.get(BASE + '/login/captcha_image?t=1')
    r = s.post(BASE + '/login/auth', data=body, allow_redirects=True, timeout=20)
    txt = r.text
    # Extract likely-flash areas: any element with text around errors
    # Look for <div class="...hint/alert/error..." or <font>
    hits = re.findall(r'<(?:div|span|p|font|td|label)[^>]*class="[^"]*(?:alert|error|danger|hint|msg|warn|info)[^"]*"[^>]*>(.*?)</(?:div|span|p|font|td|label)>', txt, re.I | re.S)
    for h in hits:
        clean = re.sub(r'<[^>]+>', '', h).strip()
        if clean:
            print(f'  flash: {clean[:200]}')
    # Also look for things containing 'verifikasi', 'captcha', 'salah', 'gagal'
    for kw in ['verifikasi', 'captcha', 'salah', 'gagal', 'tidak valid', 'harap', 'masukan']:
        for m in re.finditer(kw, txt, re.I):
            ctx = txt[max(0, m.start() - 120):m.end() + 120]
            ctx = re.sub(r'\s+', ' ', ctx)
            print(f'  kw[{kw}] ...{ctx}...')
            break
    print(f'  final={r.url} cookies={len(s.cookies)} body={len(txt)}')
    return s


s1 = probe({'username': '9999999999', 'password': 'x'}, 'no captcha')
s2 = probe({'username': '9999999999', 'password': 'x', 'captcha_answer': 'ZZZZZ'}, 'wrong captcha')