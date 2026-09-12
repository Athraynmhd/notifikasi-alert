"""Utilitas CAPTCHA: session management, fetch, segmentasi karakter, visualisasi."""

from __future__ import annotations

import io
from typing import List, Tuple

import numpy as np
import requests
from PIL import Image

from config import (
    BASE_URL,
    USER_AGENT,
    REQUEST_TIMEOUT,
    STRENGTH_SAT_STRONG,
    STRENGTH_LUM_STRONG,
    STRENGTH_SAT_SOFT,
    STRENGTH_LUM_SOFT,
    GLYPH_MIN_WIDTH,
    GLYPH_MAX_WIDTH,
    GLYPH_MAX_HEIGHT,
    GLYPH_MAX_GLYPH_WIDTH,
)


def new_session() -> requests.Session:
    """Buat HTTP session baru dengan User-Agent standar."""
    s = requests.Session()
    s.headers.update({'User-Agent': USER_AGENT})
    return s


def fetch_captcha(s: requests.Session, base: str = BASE_URL) -> bytes:
    """Fetch CAPTCHA PNG sekali (jangan fetch ulang — regenerasi kode)."""
    import re
    import time

    page = s.get(base + '/login', timeout=REQUEST_TIMEOUT)
    m = re.search(r'captcha_image\?t=(\d+)', page.text)
    t = m.group(1) if m else str(int(time.time()))
    img = s.get(base + f'/login/captcha_image?t={t}', timeout=REQUEST_TIMEOUT)
    return img.content


def read_rgb(png_bytes: bytes) -> np.ndarray:
    """Decode PNG bytes ke array RGB integer."""
    im = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    return np.array(im).astype(np.int16)


def strength(a: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Pixel-level ink strength: high saturation AND dark = char ink.

    Returns:
        (strong_mask, soft_mask) — boolean arrays ukuran (H, W).
    """
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = mx - mn
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    strong = (sat > STRENGTH_SAT_STRONG) & (lum < STRENGTH_LUM_STRONG)
    soft = (sat > STRENGTH_SAT_SOFT) & (lum < STRENGTH_LUM_SOFT)
    return strong, soft


def _glyphs_from_mask(mask: np.ndarray) -> List[Tuple[int, np.ndarray]]:
    """Segmentasi run-length dari satu binary mask."""
    col_ink = mask.sum(axis=0)
    sep = col_ink < 2
    runs: List[Tuple[int, int]] = []
    x = 0
    w = len(col_ink)
    while x < w:
        if not sep[x]:
            x0 = x
            while x < w and not sep[x]:
                x += 1
            runs.append((x0, x - 1))
        else:
            x += 1

    runs = [t for t in runs if GLYPH_MIN_WIDTH <= (t[1] - t[0] + 1) <= GLYPH_MAX_WIDTH]
    runs.sort(key=lambda t: t[1] - t[0], reverse=True)
    runs = runs[:5]
    runs.sort(key=lambda t: t[0])

    glyphs: List[Tuple[int, np.ndarray]] = []
    for (x0, x1) in runs:
        g = mask[:, x0:x1 + 1]
        rows = g.sum(axis=1)
        ys = np.where(rows > 0)[0]
        if len(ys) == 0:
            continue
        g = g[ys.min():ys.max() + 1]
        h, ww = g.shape
        if h > GLYPH_MAX_HEIGHT or ww > GLYPH_MAX_GLYPH_WIDTH:
            continue
        glyphs.append((x0, g.astype(bool)))
    return glyphs


def find_char_columns(a: np.ndarray) -> List[Tuple[int, np.ndarray]]:
    """Segmentasi 5 glyph: strong dulu, soft sebagai fallback."""
    from config import CAPTCHA_CHAR_COUNT

    strong, soft = strength(a)
    glyphs = _glyphs_from_mask(strong)
    if len(glyphs) == CAPTCHA_CHAR_COUNT:
        return glyphs
    soft_glyphs = _glyphs_from_mask(soft)
    if len(soft_glyphs) == CAPTCHA_CHAR_COUNT:
        return soft_glyphs
    # kembalikan yang lebih dekat ke 5
    return glyphs if abs(len(glyphs) - CAPTCHA_CHAR_COUNT) <= abs(
        len(soft_glyphs) - CAPTCHA_CHAR_COUNT
    ) else soft_glyphs


def ascii_art(im: np.ndarray, scale: int = 2) -> str:
    """Render binary mask sebagai ASCII art untuk debugging."""
    if not isinstance(im, np.ndarray):
        im = np.array(im)
    h, w = im.shape
    lines = []
    for y in range(0, h, scale):
        line = ''
        for x in range(0, w, scale):
            block = im[y:y + scale, x:x + scale]
            frac = block.mean()
            line += '#' if frac >= 0.4 else ('+' if frac >= 0.1 else ' ')
        if line.strip():
            lines.append(line.rstrip())
    return '\n'.join(lines)


if __name__ == '__main__':
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    for i in range(n):
        s = new_session()
        png = fetch_captcha(s)
        a = read_rgb(png)
        glyphs = find_char_columns(a)
        print('#' * 60)
        print(f'sample {i}: {len(glyphs)} leaves')
        for x0, g in glyphs:
            print(f'-- x={x0} shape={g.shape}')
            print(ascii_art(g))