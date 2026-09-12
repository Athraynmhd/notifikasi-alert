"""CAPTCHA solver berbasis Tesseract OCR.

Strategi (server meregenerasi CAPTCHA setelah jawaban salah):
- Kumpulkan hasil semua resep → vote → satu tebakan terbaik
- Soft mask hanya jika strong kosong
"""

from __future__ import annotations

import glob
import logging
import os
import subprocess
import tempfile
from collections import Counter
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageOps

import captcha_utils as cu
from config import (
    TESS_PATH,
    OCR_DIGIT_WHITELIST,
    OCR_ALNUM_WHITELIST,
    TMP_DIR,
    CAPTCHA_CHAR_COUNT,
)

log = logging.getLogger(__name__)

_RECIPES = (
    (4, '7', OCR_ALNUM_WHITELIST),
    (4, '8', OCR_ALNUM_WHITELIST),
    (3, '7', OCR_ALNUM_WHITELIST),
    (6, '7', OCR_ALNUM_WHITELIST),
    (4, '7', OCR_DIGIT_WHITELIST),
    (3, '8', OCR_ALNUM_WHITELIST),
    (6, '8', OCR_ALNUM_WHITELIST),
    (3, '7', OCR_DIGIT_WHITELIST),
)


def _ocr_file(fp: str, psm: str, whitelist: str) -> str:
    try:
        proc = subprocess.run(
            [TESS_PATH, fp, 'stdout', '--psm', psm,
             '-c', f'tessedit_char_whitelist={whitelist}'],
            capture_output=True,
            timeout=15,
            text=True,
        )
        raw = proc.stdout or ''
        return ''.join(c for c in raw if c in whitelist)
    except subprocess.TimeoutExpired:
        log.warning('Tesseract timeout pada psm=%s', psm)
        return ''
    except FileNotFoundError:
        log.error('Tesseract tidak ditemukan di: %s', TESS_PATH)
        return ''


def _votes_from_mask(mask: np.ndarray) -> List[str]:
    """Semua hasil 5-char dari resep OCR pada satu mask (bukan unique set)."""
    full = Image.fromarray((mask.astype(np.uint8) * 255))
    w, h = full.size
    votes: List[str] = []
    scale_files: dict[int, str] = {}
    try:
        for sc, psm, wh in _RECIPES:
            if sc not in scale_files:
                big = full.resize((w * sc, h * sc), Image.LANCZOS)
                fd, fp = tempfile.mkstemp(suffix='.png', dir=TMP_DIR)
                os.close(fd)
                big.save(fp)
                scale_files[sc] = fp
            text = _ocr_file(scale_files[sc], psm, wh).upper()
            if len(text) == CAPTCHA_CHAR_COUNT:
                votes.append(text)
    finally:
        for fp in scale_files.values():
            try:
                os.remove(fp)
            except OSError:
                pass
    return votes


def _votes_glyphs(a: np.ndarray) -> List[str]:
    glyphs = cu.find_char_columns(a)
    if len(glyphs) != CAPTCHA_CHAR_COUNT:
        return []
    line: List[str] = []
    for _, g in glyphs:
        gi = Image.fromarray((g.astype(np.uint8) * 255))
        gi = ImageOps.expand(gi, border=8, fill=0)
        gi = gi.resize((gi.width * 6, gi.height * 6), Image.LANCZOS)
        fd, fp = tempfile.mkstemp(suffix='.png', dir=TMP_DIR)
        os.close(fd)
        try:
            gi.save(fp)
            r = _ocr_file(fp, '7', OCR_ALNUM_WHITELIST).upper()
        finally:
            try:
                os.remove(fp)
            except OSError:
                pass
        if not r:
            return []
        line.append(r[0])
    s = ''.join(line)
    return [s] if len(s) == CAPTCHA_CHAR_COUNT else []


def _score(text: str, count: int) -> Tuple[int, int, int]:
    """Urutan sort: vote terbanyak → lebih banyak digit → penalti huruf aneh."""
    n_digit = sum(ch.isdigit() for ch in text)
    n_alpha = sum(ch.isalpha() for ch in text)
    return (count, n_digit, -n_alpha)


# Substitusi umum OCR pada CAPTCHA numerik
_CONFUSABLE = str.maketrans({
    'O': '0', 'Q': '9', 'Z': '2', 'S': '5', 'G': '6',
    'B': '8', 'I': '1', 'L': '1', 'T': '7',
})


def _digitize(text: str) -> str:
    return text.translate(_CONFUSABLE)


def best_guess(a: np.ndarray) -> Optional[str]:
    """Satu tebakan terbaik via majority vote (untuk single-submit)."""
    strong, soft = cu.strength(a)
    votes = _votes_from_mask(strong)
    if len(votes) < 2:
        votes.extend(_votes_from_mask(soft))
    if not votes:
        votes.extend(_votes_glyphs(a))
    if not votes:
        return None

    # Tambah versi ter-digitize sebagai vote ekstra (CAPTCHA cenderung numerik)
    expanded: List[str] = []
    for v in votes:
        expanded.append(v)
        d = _digitize(v)
        if d != v and d.isdigit():
            expanded.append(d)

    tallies = Counter(expanded)
    ranked = sorted(tallies.items(), key=lambda kv: _score(kv[0], kv[1]), reverse=True)
    best = ranked[0][0]
    if best.isdigit():
        return best
    for text, cnt in ranked:
        if text.isdigit() and cnt >= ranked[0][1] - 1:
            return text
    d = _digitize(best)
    if d.isdigit():
        return d
    # Tolak sampah huruf-berat (lebih baik ERROR → captcha baru)
    if sum(ch.isdigit() for ch in best) < 3:
        return None
    return best


def candidates(a: np.ndarray, max_results: int = 1) -> List[str]:
    """Kandidat terurut; default 1 (server consume-on-wrong)."""
    strong, soft = cu.strength(a)
    votes = _votes_from_mask(strong)
    if len(votes) < 2:
        votes.extend(_votes_from_mask(soft))
    if not votes:
        votes.extend(_votes_glyphs(a))
    if not votes:
        return []

    tallies = Counter(votes)
    ranked = sorted(tallies.items(), key=lambda kv: _score(kv[0], kv[1]), reverse=True)
    out = [t for t, _ in ranked]
    if max_results > 0:
        return out[:max_results]
    return out


def cleanup_all_temp() -> int:
    count = 0
    for pattern in ('ocr_*.png', 'ocr_*.txt', 'tmp*.png'):
        for f in glob.glob(os.path.join(TMP_DIR, pattern)):
            try:
                os.remove(f)
                count += 1
            except OSError:
                pass
    return count
