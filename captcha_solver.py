"""GlyphSolver: CAPTCHA solver berbasis template matching dengan glyph dictionary.

Optimasi:
- Mega-stack: satu matmul untuk SEMUA template (bukan loop per karakter)
- Flat float32 + precomputed sums
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

import captcha_utils as cu
from config import DICT_JSON, CAPTCHA_CHAR_COUNT, SOLVER_MIN_CONF
from font_solver import to_cell

log = logging.getLogger(__name__)


class GlyphSolver:
    """CAPTCHA solver berbasis dictionary of collected glyph templates."""

    def __init__(self, dict_path: str | None = None):
        self.path = dict_path or DICT_JSON
        with open(self.path, encoding='utf-8') as f:
            raw = json.load(f)

        self.templates: Dict[str, List[np.ndarray]] = {}
        cells_flat: List[np.ndarray] = []
        labels: List[str] = []

        for lab, cells in raw.items():
            cell_arrays = [np.array(c, dtype=np.uint8) for c in cells]
            self.templates[lab] = cell_arrays
            for c in cell_arrays:
                cells_flat.append((c > 0).astype(np.float32).ravel())
                labels.append(lab)

        self.chars = sorted(self.templates)
        self._labels = labels
        if cells_flat:
            self._mega = np.stack(cells_flat, axis=0)  # (N, H*W)
            self._sums = self._mega.sum(axis=1)
        else:
            self._mega = np.zeros((0, 1), dtype=np.float32)
            self._sums = np.zeros(0, dtype=np.float32)

        # Index ranges per char untuk aggregasi cepat
        self._char_idx: Dict[str, np.ndarray] = {}
        for ch in self.chars:
            idx = [i for i, lab in enumerate(labels) if lab == ch]
            self._char_idx[ch] = np.array(idx, dtype=np.int32)

        log.debug(
            'GlyphSolver loaded: %d chars, %d total templates',
            len(self.chars),
            len(labels),
        )

    def recognize(self, glyph_mask: np.ndarray, topk: int = 3) -> List[Tuple[str, float]]:
        """Return list of (char, score) — top-k via satu matmul mega-stack."""
        if self._mega.shape[0] == 0:
            return []
        q = (to_cell(glyph_mask) > 0).astype(np.float32).ravel()
        inter = self._mega @ q
        union = self._sums + q.sum() - inter
        ious = np.where(union > 0, inter / union, 0.0)

        scores: List[Tuple[str, float]] = []
        for ch, idx in self._char_idx.items():
            if idx.size == 0:
                continue
            scores.append((ch, float(ious[idx].max())))
        scores.sort(key=lambda t: -t[1])
        return scores[:topk]

    def solve(
        self,
        img_mask: np.ndarray,
        min_conf: float = SOLVER_MIN_CONF,
    ) -> Optional[Tuple[str, List[float], list]]:
        """Return (guess, confs, glyphs) untuk full 5-char CAPTCHA."""
        del min_conf
        glyphs = cu.find_char_columns(img_mask)
        if len(glyphs) != CAPTCHA_CHAR_COUNT:
            return None
        out: List[str] = []
        confs: List[float] = []
        for _, g in glyphs:
            top = self.recognize(g)
            if not top:
                return None
            best_ch, best_s = top[0]
            out.append(best_ch)
            confs.append(best_s)
        return ''.join(out), confs, glyphs

    def solve_strict(
        self,
        img_mask: np.ndarray,
        min_conf: float = SOLVER_MIN_CONF,
    ) -> Tuple[Optional[str], float]:
        """Only return guess jika SEMUA karakter confident ≥ min_conf."""
        r = self.solve(img_mask)
        if r is None:
            return None, 0.0
        guess, confs, _ = r
        worst = float(min(confs))
        if worst < min_conf:
            return None, worst
        return guess, worst
