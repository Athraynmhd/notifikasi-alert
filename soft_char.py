"""Tiny softmax classifier di atas flattened glyph cells (overkill layer)."""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Tuple

import numpy as np

from config import CELL_H, CELL_W, DICT_JSON, DATA_DIR
from font_solver import to_cell

log = logging.getLogger(__name__)

MODEL_PATH = os.path.join(DATA_DIR, 'soft_char.npz')


class SoftmaxChar:
    """Multinomial logistic regression (softmax)."""

    def __init__(self):
        self.W: Optional[np.ndarray] = None
        self.b: Optional[np.ndarray] = None
        self.classes: List[str] = []

    @property
    def ready(self) -> bool:
        return self.W is not None and len(self.classes) > 0

    def train_from_dict(
        self,
        dict_path: str = DICT_JSON,
        epochs: int = 400,
        lr: float = 0.8,
        l2: float = 1e-3,
        digits_only: bool = True,
    ) -> None:
        with open(dict_path, encoding='utf-8') as f:
            raw = json.load(f)
        if digits_only:
            raw = {k: v for k, v in raw.items() if k.isdigit()}

        classes = sorted(raw.keys())
        if len(classes) < 2:
            log.warning('SoftmaxChar: too few classes')
            return

        cmap = {c: i for i, c in enumerate(classes)}
        Xs, ys = [], []
        for lab, cells in raw.items():
            for c in cells:
                x = np.array(c, dtype=np.float32).ravel()
                Xs.append(x)
                ys.append(cmap[lab])
        X = np.stack(Xs)
        # standardize
        mu = X.mean(axis=0)
        sd = X.std(axis=0) + 1e-6
        X = (X - mu) / sd
        y = np.array(ys)
        n, d = X.shape
        C = len(classes)
        rng = np.random.default_rng(0)
        W = rng.normal(0, 0.01, (C, d)).astype(np.float32)
        b = np.zeros(C, dtype=np.float32)

        for ep in range(epochs):
            logits = X @ W.T + b
            logits -= logits.max(axis=1, keepdims=True)
            exp = np.exp(logits)
            P = exp / exp.sum(axis=1, keepdims=True)
            Y = np.zeros_like(P)
            Y[np.arange(n), y] = 1.0
            dW = ((P - Y).T @ X) / n + l2 * W
            db = (P - Y).mean(axis=0)
            W -= lr * dW
            b -= lr * db
            if ep % 50 == 0 or ep == epochs - 1:
                acc = (P.argmax(axis=1) == y).mean()
                log.info('softmax ep=%d acc=%.3f', ep, acc)

        self.W, self.b, self.classes = W, b, classes
        self.mu, self.sd = mu, sd
        np.savez_compressed(
            MODEL_PATH, W=W, b=b, classes=np.array(classes), mu=mu, sd=sd,
        )
        log.info('SoftmaxChar saved -> %s (%d classes, %d samples)', MODEL_PATH, C, n)

    def load(self, path: str = MODEL_PATH) -> bool:
        if not os.path.exists(path):
            return False
        data = np.load(path, allow_pickle=True)
        self.W = data['W']
        self.b = data['b']
        self.classes = [str(c) for c in data['classes']]
        self.mu = data['mu'] if 'mu' in data.files else np.zeros(self.W.shape[1])
        self.sd = data['sd'] if 'sd' in data.files else np.ones(self.W.shape[1])
        return True

    def predict(self, glyph_mask: np.ndarray, topk: int = 3) -> List[Tuple[str, float]]:
        if not self.ready:
            return []
        x = to_cell(glyph_mask).astype(np.float32).ravel()
        x = (x - self.mu) / self.sd
        logits = self.W @ x + self.b
        logits -= logits.max()
        p = np.exp(logits)
        p /= p.sum()
        idx = np.argsort(-p)[:topk]
        return [(self.classes[i], float(p[i])) for i in idx]


def train_default() -> SoftmaxChar:
    m = SoftmaxChar()
    m.train_from_dict()
    return m


if __name__ == '__main__':
    from config import setup_logging
    setup_logging()
    train_default()
