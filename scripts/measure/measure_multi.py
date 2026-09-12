"""Pengukuran multi-strategi akurasi bypass CAPTCHA.

Mengumpulkan kandidat dari beberapa resep OCR, lalu validasi online
dengan dummy credentials.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

import captcha_utils as cu
import solver_ocr
from config import BASE_URL, setup_logging

DUMMY_U = '9999999999'
DUMMY_P = 'x'


def submit(s, guess: str) -> str:
    """Submit satu tebakan CAPTCHA dan klasifikasi hasilnya."""
    r = s.post(BASE_URL + '/login/auth',
               data={'username': DUMMY_U, 'password': DUMMY_P, 'captcha_answer': guess},
               allow_redirects=True, timeout=25)
    if 'Username atau Password' in r.text:
        return 'SOLVED'
    return 'WRONG'


def main():
    setup_logging()

    n = 30
    solved = used = 0
    details = []
    for i in range(n):
        s = cu.new_session()
        png = cu.fetch_captcha(s)
        a = cu.read_rgb(png)
        cands = solver_ocr.candidates(a)
        if not cands:
            details.append('no-cand')
            time.sleep(0.3)
            continue
        used += 1
        ok = False
        order = []
        for g in cands:
            r = submit(s, g)
            order.append(f'{g}={r[:3]}')
            if r == 'SOLVED':
                ok = True
                break
        solved += ok
        details.append('OK' if ok else 'FAIL:' + ' '.join(order))
        time.sleep(0.25)

    print(f'sessions with candidates: {used}/{n}')
    print(f'solved: {solved}/{used} = {round(100 * solved / used, 1)}%' if used else 'N/A')
    for d in details:
        print('  ', d)


if __name__ == '__main__':
    main()