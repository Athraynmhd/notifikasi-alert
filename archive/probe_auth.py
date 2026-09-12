import requests, re, sys

BASE = 'https://simkuliah.usk.ac.id/index.php'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
OUT = r'C:\Users\Lenovo\AppData\Local\Temp\opencode'


def fetch_captcha(s):
    r = s.get(BASE + '/login/captcha_image?t=1')
    return r.content


def probe(body, label):
    s = requests.Session()
    s.headers.update(UA)
    s.get(BASE + '/login')
    img = fetch_captcha(s)
    r = s.post(BASE + '/login/auth', data=body, allow_redirects=True, timeout=20)
    txt = r.text
    title = re.search(r'<title>([^<]*)</title>', txt)
    alert = re.search(r'(?:alert-danger|error|flash)[^>]*>\s*([^<]{3,150})', txt, re.I)
    print('=' * 70)
    print(f"[{label}] POST /login/auth")
    print(f"  captcha img bytes = {len(img)}")
    print(f"  final URL   = {r.url}")
    print(f"  HTTP        = {r.status_code}  (cookies={len(s.cookies)})")
    print(f"  title       = {title.group(1) if title else '?'}")
    print(f"  alert/msg   = {alert.group(1).strip() if alert else '(none)'}")
    if '/login' in r.url and 'auth' in r.url:
        print("  REDIRECT    = stayed on auth (likely fail)")


print(">>> PROBE ENFORCEMENT CAPTCHA  (using dummy credentials)")
probe({'username': '9999999999', 'password': 'x'}, 'A. no captcha field at all')
probe({'username': '9999999999', 'password': 'x', 'captcha_answer': ''}, 'B. empty captcha')
probe({'username': '9999999999', 'password': 'x', 'captcha_answer': 'ZZZZZ'}, 'C. wrong captcha')
probe({'username': '9999999999', 'password': 'x', 'captcha_answer': 'zzzzz'}, 'D. lowercase wrong')
probe({'username': '9999999999', 'password': '', 'captcha_answer': 'ZZZZZ'}, 'E. empty password')