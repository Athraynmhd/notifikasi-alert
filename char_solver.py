"""Per-character CAPTCHA solver — glyph IoU + FontSolver + kNN + OCR glyph.

Overkill stack untuk satu tebakan terbaik (consume-on-wrong).
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageOps

import captcha_utils as cu
import solver_ocr
from captcha_solver import GlyphSolver
from config import (
    CAPTCHA_CHAR_COUNT,
    CELL_H,
    CELL_W,
    OCR_ALNUM_WHITELIST,
    SOLVER_MIN_CONF,
    TMP_DIR,
    TESS_PATH,
)
from font_solver import FontSolver, to_cell, iou_batch
from soft_char import SoftmaxChar, MODEL_PATH

log = logging.getLogger(__name__)

_CONFUSABLE = str.maketrans({
    'O': '0', 'Q': '9', 'Z': '2', 'S': '5', 'G': '6',
    'B': '8', 'I': '1', 'L': '1', 'T': '7', 'J': '1',
})


def _digitize(ch: str) -> str:
    return ch.upper().translate(_CONFUSABLE)


class KNNCharModel:
    """kNN di atas flattened binary cells (IoU distance = 1 - IoU)."""

    def __init__(self, templates: Dict[str, List[np.ndarray]], k: int = 5):
        self.k = k
        flats: List[np.ndarray] = []
        labels: List[str] = []
        for lab, cells in templates.items():
            for c in cells:
                flats.append((c > 0).astype(np.float32).ravel())
                labels.append(lab)
        if flats:
            self.X = np.stack(flats)
            self.sums = self.X.sum(axis=1)
            self.y = np.array(labels)
        else:
            self.X = np.zeros((0, CELL_H * CELL_W), dtype=np.float32)
            self.sums = np.zeros(0)
            self.y = np.array([])

    def predict(self, glyph_mask: np.ndarray) -> List[Tuple[str, float]]:
        if self.X.shape[0] == 0:
            return []
        q = (to_cell(glyph_mask) > 0).astype(np.float32).ravel()
        inter = self.X @ q
        union = self.sums + q.sum() - inter
        ious = np.where(union > 0, inter / union, 0.0)
        idx = np.argpartition(-ious, min(self.k, len(ious) - 1))[:self.k]
        idx = idx[np.argsort(-ious[idx])]
        votes: Counter[str] = Counter()
        weight: Dict[str, float] = {}
        for i in idx:
            lab = str(self.y[i])
            votes[lab] += 1
            weight[lab] = max(weight.get(lab, 0.0), float(ious[i]))
        ranked = sorted(votes.keys(), key=lambda c: (votes[c], weight[c]), reverse=True)
        return [(c, weight[c]) for c in ranked]


class CharEnsemble:
    """Gabungan GlyphSolver + FontSolver + kNN + OCR per-glyph."""

    def __init__(self):
        self.glyph: Optional[GlyphSolver] = None
        self.font: Optional[FontSolver] = None
        self.knn: Optional[KNNCharModel] = None
        self.soft: Optional[SoftmaxChar] = None
        try:
            self.glyph = GlyphSolver()
            self.knn = KNNCharModel(self.glyph.templates, k=5)
            log.info('Glyph+kNN ready: %d chars', len(self.glyph.chars))
        except Exception as e:
            log.warning('GlyphSolver load fail: %s', e)
        try:
            self.soft = SoftmaxChar()
            if not self.soft.load():
                self.soft.train_from_dict()
            log.info('SoftmaxChar ready: %d classes', len(self.soft.classes))
        except Exception as e:
            log.warning('SoftmaxChar fail: %s', e)
            self.soft = None
        try:
            self.font = FontSolver()
            log.info('FontSolver ready: %d chars', len(self.font.chars))
        except Exception as e:
            log.warning('FontSolver load fail: %s', e)

    def _ocr_char(self, glyph_mask: np.ndarray) -> Optional[str]:
        gi = Image.fromarray((glyph_mask.astype(np.uint8) * 255))
        gi = ImageOps.expand(gi, border=8, fill=0)
        gi = gi.resize((max(gi.width * 6, 24), max(gi.height * 6, 24)), Image.LANCZOS)
        fd, fp = tempfile.mkstemp(suffix='.png', dir=TMP_DIR)
        os.close(fd)
        try:
            gi.save(fp)
            import subprocess
            proc = subprocess.run(
                [TESS_PATH, fp, 'stdout', '--psm', '10',
                 '-c', f'tessedit_char_whitelist={OCR_ALNUM_WHITELIST}'],
                capture_output=True, text=True, timeout=10,
            )
            raw = ''.join(c for c in (proc.stdout or '') if c in OCR_ALNUM_WHITELIST)
            return raw[0].upper() if raw else None
        except Exception:
            return None
        finally:
            try:
                os.remove(fp)
            except OSError:
                pass

    def recognize_char(self, glyph_mask: np.ndarray) -> Tuple[str, float]:
        """Return (char, confidence) dari voting multi-model."""
        votes: Counter[str] = Counter()
        confs: Dict[str, List[float]] = {}

        def add(ch: Optional[str], w: float, conf: float) -> None:
            if not ch:
                return
            ch = ch.upper()
            votes[ch] += w
            confs.setdefault(ch, []).append(conf)
            d = _digitize(ch)
            if d != ch and d.isalnum():
                votes[d] += w * 0.85
                confs.setdefault(d, []).append(conf * 0.9)

        if self.glyph is not None:
            top = self.glyph.recognize(glyph_mask, topk=3)
            for i, (ch, sc) in enumerate(top):
                add(ch, 3.0 - i * 0.7, sc)

        if self.knn is not None:
            top = self.knn.predict(glyph_mask)
            for i, (ch, sc) in enumerate(top[:3]):
                add(ch, 2.5 - i * 0.6, sc)

        if self.soft is not None and self.soft.ready:
            top = self.soft.predict(glyph_mask, topk=3)
            for i, (ch, sc) in enumerate(top):
                add(ch, 2.8 - i * 0.7, sc)

        if self.font is not None:
            try:
                top = self.font.recognize(glyph_mask, topk=3)
                for i, (ch, sc) in enumerate(top):
                    add(ch, 1.5 - i * 0.4, sc)
            except Exception:
                pass

        oc = self._ocr_char(glyph_mask)
        if oc:
            add(oc, 1.2, 0.55)

        if not votes:
            return '?', 0.0

        best = max(votes.keys(), key=lambda c: (votes[c], max(confs.get(c, [0]))))
        conf = float(max(confs.get(best, [0.0])))
        # boost conf jika banyak model setuju
        if votes[best] >= 4:
            conf = max(conf, 0.75)
        return best, conf

    def solve(self, img) -> Optional[Tuple[str, List[float]]]:
        glyphs = cu.find_char_columns(img)
        if len(glyphs) != CAPTCHA_CHAR_COUNT:
            return None
        chars: List[str] = []
        confs: List[float] = []
        for _, g in glyphs:
            ch, cf = self.recognize_char(g)
            if ch == '?':
                return None
            chars.append(ch)
            confs.append(cf)
        return ''.join(chars), confs


class UltimateSolver:
    """Single-guess solver: CharEnsemble + whole-image OCR vote + digitize."""

    def __init__(self):
        self.chars = CharEnsemble()

    def best_guess(self, img) -> Optional[str]:
        cands: Counter[str] = Counter()

        # 1) per-char ensemble
        r = self.chars.solve(img)
        if r is not None:
            guess, confs = r
            w = 3.0 if min(confs) >= SOLVER_MIN_CONF else 1.5
            cands[guess] += w
            d = guess.translate(_CONFUSABLE)
            if d != guess and d.isdigit():
                cands[d] += w * 1.1  # prefer digitized

        # 2) whole-image OCR vote
        ocr = solver_ocr.best_guess(img)
        if ocr:
            cands[ocr] += 2.0
            d = ocr.translate(_CONFUSABLE)
            if d != ocr and d.isdigit():
                cands[d] += 2.2

        if not cands:
            return None

        def score(text: str) -> Tuple:
            n_digit = sum(ch.isdigit() for ch in text)
            return (cands[text], n_digit, -sum(ch.isalpha() for ch in text))

        best = max(cands.keys(), key=score)
        if sum(ch.isdigit() for ch in best) < 3:
            # coba digitize
            d = best.translate(_CONFUSABLE)
            if d.isdigit():
                return d
            return None
        if not best.isdigit():
            d = best.translate(_CONFUSABLE)
            if d.isdigit() and cands.get(d, 0) >= cands[best] * 0.7:
                return d
        return best


_ultimate: Optional[UltimateSolver] = None


def get_solver(force_reload: bool = False) -> UltimateSolver:
    global _ultimate
    if force_reload or _ultimate is None:
        _ultimate = UltimateSolver()
    return _ultimate
