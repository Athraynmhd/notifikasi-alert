"""Oracle test: validasi online akurasi GlyphSolver dengan dummy credentials.

Menggunakan kredensial dummy sehingga respons server hanya mengungkap
apakah JAWABAN CAPTCHA benar — bukan akses nyata.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

import captcha_utils as cu
from captcha_solver import GlyphSolver
from config import BASE_URL, setup_logging

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
MIN_CONF = float(sys.argv[2]) if len(sys.argv) > 2 else 0.60
DUMMY_U = '9999999999'
DUMMY_P = 'x'


def classify(r, guess):
    txt = r.text
    # known wrong-captcha flash:
    if 'Kode verifikasi' in txt or 'captcha' in txt.lower():
        return 'WRONG_CAPTCHA'
    if '/absensi' in r.url or '/dashboard' in r.url or '/main' in r.url:
        return 'LOGIN_OK'
    # unknown message class -> need investigation
    alert = re.search(
        r'(alert-(?:danger|warning|info|success)|flash)[^>]*>\s*([^<]{4,200})',
        txt, re.I,
    )
    msg = alert.group(2).strip() if alert else ''
    title_m = re.search(r'<title>([^<]*)</title>', txt, re.I)
    title = title_m.group(1) if title_m else ''
    return 'OTHER:' + (msg[:80] if msg else title)


def one(solver: GlyphSolver, iter_i: int):
    """Satu percobaan: fetch captcha → solve → submit → classify."""
    s = cu.new_session()
    png = cu.fetch_captcha(s)
    a = cu.read_rgb(png)
    guess, min_conf = solver.solve_strict(a, min_conf=MIN_CONF)
    if guess is None:
        return None
    r = s.post(BASE_URL + '/login/auth',
               data={'username': DUMMY_U, 'password': DUMMY_P,
                     'captcha_answer': guess},
               allow_redirects=True, timeout=25)
    cls = classify(r, guess)
    return {'guess': guess, 'min_conf': round(min_conf, 3), 'class': cls,
            'url': r.url}


def main():
    setup_logging()

    # ★ Inisialisasi solver SEKALI — bukan di setiap iterasi
    solver = GlyphSolver()

    print(f'oracle test: N={N}, min_conf={MIN_CONF}, dummy creds {DUMMY_U}:{DUMMY_P}')
    print('-' * 60)
    hits = {k: 0 for k in ('WRONG_CAPTCHA', 'LOGIN_OK', 'OTHER')}
    guesses = []
    solved = 0
    attempts = 0
    while solved < N and attempts < N * 6:
        attempts += 1
        try:
            out = one(solver, attempts)
        except Exception as e:
            print(f'  [attempt {attempts}] err {e}')
            time.sleep(1)
            continue
        if out is None:
            continue
        solved += 1
        hits[out['class']] = hits.get(out['class'], 0) + 1
        guesses.append(out)
        flag = 'PASS' if out['class'] != 'WRONG_CAPTCHA' else 'rej '
        print(f"  [#{solved}] conf={out['min_conf']} guess={out['guess']}"
              f" -> {out['class']}  [{flag}]")
        time.sleep(0.5)

    print('-' * 60)
    print(f'captchas evaluated: {solved}, low-conf rejected: {attempts - solved}')
    for k, v in hits.items():
        if v:
            print(f'  {k}: {v}')
    bypass = hits.get('LOGIN_OK', 0) + hits.get('OTHER', 0)
    print(f'solved captchas that got past captcha gate: {bypass}/{solved}')
    if hits.get('WRONG_CAPTCHA', 0):
        print('estimate per-attempt accuracy = ',
              round((solved - hits.get('WRONG_CAPTCHA', 0)) / solved, 3))


if __name__ == '__main__':
    main()