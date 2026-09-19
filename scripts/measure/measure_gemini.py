"""Ukur akurasi Gemini Vision vs login dummy (CAPTCHA benar = BAD_CREDS).

Usage:
  python scripts/measure/measure_gemini.py 10
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

# Load .env dari root
_env = Path(__file__).resolve().parents[2] / '.env'
if _env.exists():
    for line in _env.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

from collections import Counter

import captcha_utils as cu
import solver_gemini
import simkuliah
from config import setup_logging, CAPTCHA_CHAR_COUNT


def main() -> int:
    setup_logging()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    stats: Counter[str] = Counter()

    for i in range(1, n + 1):
        s = cu.new_session()
        try:
            png = cu.fetch_captcha(s)
        except Exception as e:
            print(f'[{i}/{n}] FETCH_FAIL {e}')
            stats['fetch_fail'] += 1
            continue

        guess = solver_gemini.best_guess(png)
        if not guess or len(guess) != CAPTCHA_CHAR_COUNT:
            print(f'[{i}/{n}] NO_GUESS raw={guess!r}')
            stats['no_guess'] += 1
            continue

        # Validasi online: dummy creds → BAD_CREDS = captcha benar
        c = simkuliah.SIMKULIAH()
        c.session = s
        c._last_captcha_png = png
        kind, msg = c._post_login('9999999999', 'x', guess)
        print(f'[{i}/{n}] guess={guess} -> {kind} ({msg})')
        stats[kind] += 1

    print('---')
    print(dict(stats))
    solved = stats.get('BAD_CREDS', 0)  # captcha OK
    tried = sum(stats[k] for k in stats if k != 'fetch_fail')
    if tried:
        print(f'CAPTCHA ok rate: {solved}/{tried} = {100 * solved / tried:.0f}%')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
