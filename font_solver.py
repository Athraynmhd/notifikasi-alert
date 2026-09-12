"""Font-based CAPTCHA solver: render font templates, match via IOU.

Optimasi:
- Template rendering di-cache ke disk (.npz)
- Vectorized batch IOU; mendukung stack float32 pra-flatten
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import (
    FONT_DIR,
    CELL_H,
    CELL_W,
    CANDIDATE_FONTS,
    CHARSET,
    FONT_CACHE_NPZ,
)

log = logging.getLogger(__name__)


def _exists(f: str) -> bool:
    return os.path.exists(os.path.join(FONT_DIR, f))


def render_char(font_path: str, ch: str, target_h: int = 34) -> Optional[np.ndarray]:
    """Render satu karakter dari font, binarize (anti-aliased → ink if alpha strong)."""
    probe = Image.new('L', (200, 200), 0)
    d = ImageDraw.Draw(probe)
    sz = 80
    f = ImageFont.truetype(font_path, sz)
    bbox = d.textbbox((100, 100), ch, font=f)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if bw <= 0 or bh <= 0:
        return None
    scale = target_h / bh
    img = Image.new('L', (200, 200), 0)
    d = ImageDraw.Draw(img)
    d.text((100, 100), ch, font=f, fill=255)
    arr = np.array(img)
    mask = arr > 128
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = mask[y0:y1 + 1, x0:x1 + 1].astype(np.uint8)
    h2, w2 = crop.shape
    nh = max(4, int(round(h2 * scale))) + 1
    nw = max(4, int(round(w2 * scale * 1.15))) + 1
    im2 = Image.fromarray(crop * 255).resize((nw, nh), Image.LANCZOS)
    return np.array(im2) > 100


def to_cell(mask: np.ndarray, cell_h: int = CELL_H, cell_w: int = CELL_W) -> np.ndarray:
    """Fit binary glyph into a cell, preserving aspect ratio, centered."""
    mask = (mask > 0).astype(np.uint8)
    if mask.max() == 0:
        return np.zeros((cell_h, cell_w), dtype=np.uint8)
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return np.zeros((cell_h, cell_w), dtype=np.uint8)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    scale = min((cell_h - 4) / h, (cell_w - 4) / w)
    nh = max(1, int(round(h * scale)))
    nw = max(1, int(round(w * scale)))
    im = Image.fromarray(crop * 255).resize((nw, nh), Image.LANCZOS)
    a = (np.array(im) > 100).astype(np.uint8)
    cell = np.zeros((cell_h, cell_w), dtype=np.uint8)
    y = (cell_h - nh) // 2
    x = (cell_w - nw) // 2
    cell[y:y + nh, x:x + nw] = a
    return cell


def iou(a: np.ndarray, b: np.ndarray) -> float:
    """Intersection-over-Union antara dua binary masks."""
    a = a > 0
    b = b > 0
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def iou_batch(
    query: np.ndarray,
    templates: np.ndarray,
    template_sums: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Vectorized IOU: satu query (H,W) vs N templates.

    templates: (N,H,W) uint8/bool ATAU (N, H*W) float32 pra-flatten.
    template_sums: opsional (N,) — jumlah ink per template (hindari re-sum).
    """
    q = (query > 0).astype(np.float32).ravel()
    if templates.ndim == 3:
        t_flat = (templates > 0).astype(np.float32).reshape(templates.shape[0], -1)
    else:
        t_flat = templates.astype(np.float32, copy=False)
    inter = t_flat @ q
    tsum = template_sums if template_sums is not None else t_flat.sum(axis=1)
    union = tsum + q.sum() - inter
    return np.where(union > 0, inter / union, 0.0)


class FontSolver:
    """CAPTCHA solver berbasis template matching dengan rendered system fonts."""

    def __init__(self, cache_path: str = FONT_CACHE_NPZ):
        self.templates: Dict[str, List[np.ndarray]] = {}
        self._stacked: Dict[str, np.ndarray] = {}
        self._flat: Dict[str, np.ndarray] = {}
        self._sums: Dict[str, np.ndarray] = {}

        if os.path.exists(cache_path):
            self._load_cache(cache_path)
        else:
            self._render_all()
            self._save_cache(cache_path)

        self._precompute_stacked()
        self.chars = sorted(self.templates)

    def _render_all(self) -> None:
        present = [f for f in CANDIDATE_FONTS if _exists(f)]
        log.info('Rendering templates dari %d font...', len(present))
        for f in present:
            ft = os.path.join(FONT_DIR, f)
            for ch in CHARSET:
                try:
                    r = render_char(ft, ch)
                except Exception:
                    continue
                if r is None:
                    continue
                self.templates.setdefault(ch, []).append(to_cell(r))

    def _save_cache(self, path: str) -> None:
        save_dict = {}
        for ch, cells in self.templates.items():
            key = f'char_{ord(ch)}'
            save_dict[key] = np.array(cells, dtype=np.uint8)
        np.savez_compressed(path, **save_dict)
        log.info('Font cache disimpan ke %s (%d chars)', path, len(save_dict))

    def _load_cache(self, path: str) -> None:
        data = np.load(path)
        for key in data.files:
            ch = chr(int(key.split('_')[1]))
            self.templates[ch] = [row for row in data[key]]
        log.info('Font cache di-load dari %s (%d chars)', path, len(self.templates))

    def _precompute_stacked(self) -> None:
        for ch, cells in self.templates.items():
            if not cells:
                continue
            stack = np.array(cells, dtype=np.uint8)
            self._stacked[ch] = stack
            flat = (stack > 0).astype(np.float32).reshape(stack.shape[0], -1)
            self._flat[ch] = flat
            self._sums[ch] = flat.sum(axis=1)

    def recognize(self, glyph_mask: np.ndarray, topk: int = 3) -> List[Tuple[str, float]]:
        q = to_cell(glyph_mask)
        scores = []
        for ch in self.chars:
            flat = self._flat.get(ch)
            if flat is None:
                continue
            best = float(iou_batch(q, flat, self._sums[ch]).max())
            scores.append((ch, best))
        scores.sort(key=lambda t: -t[1])
        return scores[:topk]


if __name__ == '__main__':
    from config import setup_logging
    setup_logging()
    fs = FontSolver()
    print('fonts used:', len(fs.templates))
    print('chars:', fs.chars)
    for ch in ['A', 'B', '2', 'Z', 'R', 'K', 'S', '3', '5', '7', 'O', '0']:
        if ch not in fs.templates:
            continue
        s = fs.recognize(fs.templates[ch][0])
        print(f'  self-match {ch} -> {s[:3]}')
