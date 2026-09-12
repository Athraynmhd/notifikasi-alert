"""Panen label CAPTCHA terverifikasi (dummy login) → perluas glyph_dict.

Alur:
1. Fetch captcha
2. Tebak via OCR vote
3. Submit dummy → jika BAD_CREDS, string BENAR
4. Segment 5 glyph, simpan template per karakter
5. Merge ke glyph_dict.json

Usage:
  python scripts/training/harvest_labels.py 40
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

import numpy as np

import captcha_utils as cu
import solver_ocr
from config import (
    BASE_URL,
    DICT_JSON,
    REQUEST_TIMEOUT,
    CAPTCHA_CHAR_COUNT,
    setup_logging,
)
from font_solver import to_cell

log = logging.getLogger(__name__)


def load_dict(path: str = DICT_JSON) -> dict[str, list]:
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_dict(data: dict[str, list], path: str = DICT_JSON) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    counts = {k: len(v) for k, v in sorted(data.items())}
    log.info('saved %s — %d chars, %d templates %s',
             path, len(data), sum(counts.values()), counts)


def submit_dummy(session, guess: str) -> str:
    r = session.post(
        BASE_URL + '/login/auth',
        data={'username': '9999999999', 'password': 'x', 'captcha_answer': guess},
        allow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    )
    if 'Username atau Password' in r.text:
        return 'SOLVED'
    if 'Kode verifikasi' in r.text or 'verifikasi' in r.text.lower():
        return 'WRONG'
    return 'OTHER'


def harvest(target_solved: int = 40, max_fetches: int = 120) -> None:
    data = load_dict()
    # dedupe set per char via tuple of flat bytes
    seen: dict[str, set[bytes]] = defaultdict(set)
    for ch, cells in data.items():
        for c in cells:
            seen[ch].add(np.array(c, dtype=np.uint8).tobytes())

    solved = added = 0
    fetches = 0
    while solved < target_solved and fetches < max_fetches:
        fetches += 1
        s = cu.new_session()
        try:
            png = cu.fetch_captcha(s)
            a = cu.read_rgb(png)
        except Exception as e:
            log.warning('fetch fail: %s', e)
            time.sleep(0.5)
            continue

        guess = solver_ocr.best_guess(a)
        if not guess:
            log.info('[%d] no guess', fetches)
            time.sleep(0.25)
            continue

        status = submit_dummy(s, guess)
        log.info('[%d] guess=%s -> %s', fetches, guess, status)
        if status != 'SOLVED':
            time.sleep(0.3)
            continue

        solved += 1
        glyphs = cu.find_char_columns(a)
        if len(glyphs) != CAPTCHA_CHAR_COUNT:
            log.warning('  solved but glyphs=%d — skip store', len(glyphs))
            time.sleep(0.3)
            continue

        for ch, (_, g) in zip(guess, glyphs):
            cell = to_cell(g).astype(np.uint8)
            key = cell.tobytes()
            if key in seen[ch]:
                continue
            seen[ch].add(key)
            data.setdefault(ch, []).append(cell.tolist())
            added += 1

        time.sleep(0.35)

    save_dict(data)
    print(f'solved={solved}/{fetches} fetches, new_templates={added}')


if __name__ == '__main__':
    setup_logging()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    harvest(n)
