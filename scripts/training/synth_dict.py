"""Generate glyph_dict dari font sintetis — tanpa labeling manual.

1. Skor font sistem vs template hasil harvest (IoU)
2. Ambil top fonts
3. Render 0-9 (+ huruf) dengan variasi skala/tebal
4. Merge ke glyph_dict (harvest tetap diprioritaskan)

Usage:
  python scripts/training/synth_dict.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.repo_path  # noqa: F401

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from config import (
    FONT_DIR,
    CANDIDATE_FONTS,
    DICT_JSON,
    CELL_H,
    CELL_W,
    setup_logging,
)
from font_solver import to_cell, iou, render_char, _exists

log = logging.getLogger(__name__)

DIGIT_CHARS = '0123456789'
# Huruf yang sering muncul di CAPTCHA historis
EXTRA_CHARS = 'JQSZG'


def load_dict(path: str = DICT_JSON) -> Dict[str, List[np.ndarray]]:
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    return {k: [np.array(c, dtype=np.uint8) for c in v] for k, v in raw.items()}


def save_dict(data: Dict[str, List[np.ndarray]], path: str = DICT_JSON) -> None:
    out = {k: [c.astype(np.uint8).tolist() for c in v] for k, v in data.items()}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f)
    counts = {k: len(v) for k, v in sorted(data.items())}
    log.info('saved %s — %d chars, %d tpl %s', path, len(data), sum(counts.values()), counts)


def render_variants(font_path: str, ch: str) -> List[np.ndarray]:
    """Render karakter dengan beberapa tinggi + dilate/erode ringan."""
    cells: List[np.ndarray] = []
    for th in (28, 32, 34, 36, 38):
        try:
            mask = render_char(font_path, ch, target_h=th)
        except Exception:
            continue
        if mask is None:
            continue
        base = to_cell(mask)
        cells.append(base)
        # tebalkan / tipiskan stroke
        im = Image.fromarray(base * 255)
        for rad in (1,):
            dil = im.filter(ImageFilter.MaxFilter(rad * 2 + 1))
            cells.append(to_cell(np.array(dil) > 100))
            ero = im.filter(ImageFilter.MinFilter(rad * 2 + 1))
            cells.append(to_cell(np.array(ero) > 100))
    # dedupe
    uniq, seen = [], set()
    for c in cells:
        k = c.tobytes()
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


def score_font(font_file: str, ref: Dict[str, List[np.ndarray]]) -> float:
    """Rata-rata best-IoU font vs harvested digit templates."""
    path = os.path.join(FONT_DIR, font_file)
    scores = []
    for ch in DIGIT_CHARS:
        refs = ref.get(ch) or []
        if not refs:
            continue
        try:
            m = render_char(path, ch, target_h=34)
        except Exception:
            continue
        if m is None:
            continue
        cell = to_cell(m)
        best = max(iou(cell, r) for r in refs[:12])  # sample
        scores.append(best)
    return float(np.mean(scores)) if scores else 0.0


def pick_fonts(ref: Dict[str, List[np.ndarray]], top_k: int = 5) -> List[Tuple[str, float]]:
    present = [f for f in CANDIDATE_FONTS if _exists(f)]
    # tambah font umum Windows jika ada
    extras = [
        'arialbd.ttf', 'arial.ttf', 'comic.ttf', 'comicbd.ttf',
        'impact.ttf', 'lucon.ttf', 'courbd.ttf', 'cour.ttf',
        'georgia.ttf', 'georgiab.ttf', 'micross.ttf', 'consolab.ttf',
        'verdana.ttf', 'verdanab.ttf', 'tahoma.ttf', 'tahomabd.ttf',
        'seguisb.ttf', 'segoeuib.ttf', 'calibrib.ttf', 'framd.ttf',
        'framdit.ttf', 'DejaVuSans-Bold.ttf',
    ]
    for e in extras:
        if e not in present and _exists(e):
            present.append(e)

    ranked = []
    for f in present:
        s = score_font(f, ref)
        ranked.append((f, s))
        log.info('font %-20s score=%.3f', f, s)
    ranked.sort(key=lambda t: -t[1])
    return ranked[:top_k]


def merge(
    harvested: Dict[str, List[np.ndarray]],
    synthetic: Dict[str, List[np.ndarray]],
    max_per_char: int = 80,
) -> Dict[str, List[np.ndarray]]:
    out: Dict[str, List[np.ndarray]] = {}
    chars = sorted(set(harvested) | set(synthetic))
    for ch in chars:
        seen = set()
        merged: List[np.ndarray] = []
        for src in (harvested.get(ch, []), synthetic.get(ch, [])):
            for c in src:
                k = c.tobytes()
                if k in seen:
                    continue
                seen.add(k)
                merged.append(c)
                if len(merged) >= max_per_char:
                    break
            if len(merged) >= max_per_char:
                break
        if merged:
            out[ch] = merged
    return out


def main() -> None:
    setup_logging()
    harvested = load_dict()
    log.info('harvested: %d chars, %d tpl',
             len(harvested), sum(len(v) for v in harvested.values()))

    top = pick_fonts(harvested, top_k=5)
    log.info('TOP fonts: %s', top)
    if not top or top[0][1] < 0.15:
        log.warning('Font match lemah — tetap generate dari top yang ada')

    synthetic: Dict[str, List[np.ndarray]] = {}
    charset = DIGIT_CHARS + EXTRA_CHARS
    for font_file, sc in top:
        path = os.path.join(FONT_DIR, font_file)
        log.info('rendering %s (score=%.3f)...', font_file, sc)
        for ch in charset:
            cells = render_variants(path, ch)
            synthetic.setdefault(ch, []).extend(cells)

    merged = merge(harvested, synthetic)
    save_dict(merged)

    # tulis meta font terbaik
    meta_path = os.path.join(os.path.dirname(DICT_JSON), 'best_fonts.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump([{'font': a, 'score': b} for a, b in top], f, indent=2)
    log.info('best fonts -> %s', meta_path)


if __name__ == '__main__':
    main()
