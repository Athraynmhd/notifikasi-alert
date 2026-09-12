"""CAPTCHA solver: Glyph IoU + Softmax + whole-image OCR (single guess).

ponytail: FontSolver + kNN dihapus — overlap dengan Glyph/Softmax, startup mahal.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

import captcha_utils as cu
import solver_ocr
from captcha_solver import GlyphSolver
from config import CAPTCHA_CHAR_COUNT, SOLVER_MIN_CONF
from soft_char import SoftmaxChar

log = logging.getLogger(__name__)

_CONFUSABLE = str.maketrans({
    'O': '0', 'Q': '9', 'Z': '2', 'S': '5', 'G': '6',
    'B': '8', 'I': '1', 'L': '1', 'T': '7', 'J': '1',
})


def _digitize(text: str) -> str:
    return text.upper().translate(_CONFUSABLE)


class CharEnsemble:
    """Glyph template + Softmax per karakter."""

    def __init__(self):
        self.glyph: Optional[GlyphSolver] = None
        self.soft: Optional[SoftmaxChar] = None
        try:
            self.glyph = GlyphSolver()
            log.info('GlyphSolver ready: %d chars', len(self.glyph.chars))
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

    def recognize_char(self, glyph_mask) -> Tuple[str, float]:
        votes: Counter[str] = Counter()
        confs: Dict[str, List[float]] = {}

        def add(ch: Optional[str], w: float, conf: float) -> None:
            if not ch:
                return
            ch = ch.upper()
            votes[ch] += w
            confs.setdefault(ch, []).append(conf)
            d = _digitize(ch)
            if d != ch and len(d) == 1:
                votes[d] += w * 0.85
                confs.setdefault(d, []).append(conf * 0.9)

        if self.glyph is not None:
            for i, (ch, sc) in enumerate(self.glyph.recognize(glyph_mask, topk=3)):
                add(ch, 3.0 - i * 0.7, sc)

        if self.soft is not None and self.soft.ready:
            for i, (ch, sc) in enumerate(self.soft.predict(glyph_mask, topk=3)):
                add(ch, 2.5 - i * 0.6, sc)

        if not votes:
            return '?', 0.0
        best = max(votes, key=lambda c: (votes[c], max(confs.get(c, [0]))))
        conf = float(max(confs.get(best, [0.0])))
        if votes[best] >= 3:
            conf = max(conf, 0.75)
        return best, conf

    def solve(self, img) -> Optional[Tuple[str, List[float]]]:
        glyphs = cu.find_char_columns(img)
        if len(glyphs) != CAPTCHA_CHAR_COUNT:
            return None
        chars, confs = [], []
        for _, g in glyphs:
            ch, cf = self.recognize_char(g)
            if ch == '?':
                return None
            chars.append(ch)
            confs.append(cf)
        return ''.join(chars), confs


class UltimateSolver:
    """Glyph/Softmax dulu; OCR whole-image hanya jika conf rendah."""

    def __init__(self):
        self.chars = CharEnsemble()

    def best_guess(self, img) -> Optional[str]:
        cands: Counter[str] = Counter()
        high_conf = False

        r = self.chars.solve(img)
        if r is not None:
            guess, confs = r
            worst = min(confs)
            high_conf = worst >= SOLVER_MIN_CONF
            w = 3.0 if high_conf else 1.5
            cands[guess] += w
            d = _digitize(guess)
            if d != guess and d.isdigit():
                cands[d] += w * 1.1

        # ponytail: skip OCR mahal jika glyph sudah yakin
        if not high_conf:
            ocr = solver_ocr.best_guess(img)
            if ocr:
                cands[ocr] += 2.0
                d = _digitize(ocr)
                if d != ocr and d.isdigit():
                    cands[d] += 2.2

        if not cands:
            return None

        def score(text: str) -> Tuple:
            return (cands[text], sum(ch.isdigit() for ch in text), -sum(ch.isalpha() for ch in text))

        best = max(cands, key=score)
        if best.isdigit():
            return best
        d = _digitize(best)
        if d.isdigit():
            return d
        if sum(ch.isdigit() for ch in best) < 3:
            return None
        return best


_ultimate: Optional[UltimateSolver] = None


def get_solver(force_reload: bool = False) -> UltimateSolver:
    global _ultimate
    if force_reload or _ultimate is None:
        _ultimate = UltimateSolver()
    return _ultimate
