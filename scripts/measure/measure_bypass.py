"""Pengukuran tingkat keberhasilan bypass CAPTCHA (metrik riset).

Satu tebakan per attempt — server meregenerasi CAPTCHA setelah jawaban salah.
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

import simkuliah
from config import setup_logging


def main():
    setup_logging()

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    c = simkuliah.SIMKULIAH()
    stats: Counter[str] = Counter()
    cres: Counter[str] = Counter()

    for i in range(n):
        kind, msg = c.login_attempt('9999999999', 'x')
        stats[kind] += 1
        if kind in ('BAD_CREDS', 'LOGIN_OK'):
            cres['captcha_solved'] += 1
        elif kind == 'WRONG_CAPTCHA':
            cres['captcha_wrong'] += 1
        else:
            cres['unreadable/err'] += 1
        print(f'  #{i + 1}: {kind}')
        time.sleep(0.3)

    total = cres['captcha_solved'] + cres['captcha_wrong']
    print('-' * 55)
    print('outcomes:', dict(stats))
    print(f'captcha read & attempted: {total}')
    if total:
        print(f'captcha bypass rate: {cres["captcha_solved"]}/{total} = '
              f'{round(100 * cres["captcha_solved"] / total, 1)}%')
    print('unreadable/err (len!=5):', cres['unreadable/err'])


if __name__ == '__main__':
    main()