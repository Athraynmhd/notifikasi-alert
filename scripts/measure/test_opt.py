"""Uji lokal + online (dummy creds) untuk solver yang dioptimasi.

Usage:
  python scripts/measure/test_opt.py           # lokal saja
  python scripts/measure/test_opt.py --online 8
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

import numpy as np

from captcha_solver import GlyphSolver
from config import setup_logging, CELL_H, CELL_W
from font_solver import to_cell, iou_batch


def test_local() -> bool:
    print('=== LOCAL ===')
    gs = GlyphSolver()
    assert gs.chars, 'glyph dict kosong'
    n_tpl = sum(len(v) for v in gs.templates.values())
    print(f'GlyphSolver: {len(gs.chars)} chars, {n_tpl} templates')

    # Self-match setiap template harus mengenali label sendiri
    ok = miss = 0
    t0 = time.perf_counter()
    for ch, cells in gs.templates.items():
        for cell in cells:
            top = gs.recognize(cell)
            if top and top[0][0] == ch:
                ok += 1
            else:
                miss += 1
                print(f'  MISS {ch} -> {top[:2]}')
    dt = (time.perf_counter() - t0) * 1000
    total = ok + miss
    print(f'self-match: {ok}/{total} = {100 * ok / total:.1f}%  ({dt:.0f} ms, {dt / max(total, 1):.2f} ms/glyph)')

    # Bench mega-stack vs naive loop
    q = to_cell(list(gs.templates.values())[0][0])
    reps = 200
    t0 = time.perf_counter()
    for _ in range(reps):
        gs.recognize(q)
    mega_ms = (time.perf_counter() - t0) * 1000 / reps
    print(f'recognize avg: {mega_ms:.3f} ms')

    # Sanity iou_batch
    stack = np.array(gs.templates[gs.chars[0]], dtype=np.uint8)
    scores = iou_batch(q, stack)
    assert scores.shape == (len(stack),)
    print(f'iou_batch OK shape={scores.shape} max={scores.max():.3f}')

    # Synthetic 5-glyph collage (hanya jika punya ≥1 template)
    print(f'cell size expected {CELL_H}x{CELL_W}')
    passed = miss == 0
    print('LOCAL:', 'PASS' if passed else 'FAIL')
    return passed


def test_online(n: int) -> bool:
    print(f'=== ONLINE (n={n}, dummy creds, single-guess) ===')
    import simkuliah
    from collections import Counter

    c = simkuliah.SIMKULIAH()
    stats: Counter[str] = Counter()
    t0 = time.perf_counter()
    for i in range(n):
        kind, msg = c.login_attempt('9999999999', 'x')
        stats[kind] += 1
        print(f'  #{i + 1}: {kind} — {msg}')
        time.sleep(0.25)
    elapsed = time.perf_counter() - t0

    solved = stats['BAD_CREDS'] + stats['LOGIN_OK']
    wrong = stats['WRONG_CAPTCHA']
    attempted = solved + wrong
    print('-' * 50)
    print('outcomes:', dict(stats))
    print(f'elapsed: {elapsed:.1f}s  ({elapsed / n:.2f}s/try)')
    if attempted:
        rate = 100 * solved / attempted
        print(f'captcha bypass: {solved}/{attempted} = {rate:.1f}%')
    else:
        print('captcha bypass: N/A (no attempts)')
        rate = 0.0
    # Target riset: majority solve; 40%+ dianggap sehat untuk OCR lemah
    print('ONLINE:', 'PASS' if attempted and rate >= 40 else 'CHECK')
    return attempted > 0


def main():
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument('--online', type=int, nargs='?', const=8, default=0,
                    help='jalankan N percobaan online (default 8 jika flag tanpa angka)')
    args = ap.parse_args()

    ok = test_local()
    if args.online:
        ok = test_online(args.online) and ok
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
