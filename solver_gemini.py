"""CAPTCHA solver via Gemini Vision API (primary production path)."""

from __future__ import annotations

import base64
import logging
import os
import re
from typing import Optional

import requests

from config import CAPTCHA_CHAR_COUNT, REQUEST_TIMEOUT

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash-lite').strip()

_API = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    '{model}:generateContent'
)

_PROMPT = (
    'This image is a login CAPTCHA with exactly 5 characters '
    '(digits 0-9 and/or letters). '
    'Read the characters carefully in left-to-right order. '
    'Reply with ONLY the 5 characters, nothing else — no spaces, no quotes, no explanation.'
)


def _normalize(text: str) -> Optional[str]:
    if not text:
        return None
    # Ambil alnum saja, buang markdown/petik
    cleaned = re.sub(r'[^A-Za-z0-9]', '', text.strip())
    if len(cleaned) == CAPTCHA_CHAR_COUNT:
        return cleaned
    # Kadang model balas lebih panjang — ambil 5 pertama yang masuk akal
    m = re.search(r'[A-Za-z0-9]{%d}' % CAPTCHA_CHAR_COUNT, cleaned)
    return m.group(0) if m else None


def best_guess(png_bytes: bytes, *, api_key: Optional[str] = None, model: Optional[str] = None) -> Optional[str]:
    """Solve CAPTCHA PNG via Gemini. Return 5-char string or None."""
    key = (api_key or GEMINI_API_KEY or '').strip()
    if not key:
        log.warning('GEMINI_API_KEY kosong — skip vision solver')
        return None
    mdl = (model or GEMINI_MODEL or 'gemini-3.1-flash-lite').strip()
    # API kadang minta nama tanpa prefix models/
    if mdl.startswith('models/'):
        mdl = mdl[len('models/'):]

    b64 = base64.b64encode(png_bytes).decode('ascii')
    url = _API.format(model=mdl)
    payload = {
        'contents': [{
            'parts': [
                {'text': _PROMPT},
                {'inline_data': {'mime_type': 'image/png', 'data': b64}},
            ],
        }],
        'generationConfig': {
            'temperature': 0.0,
            'maxOutputTokens': 64,
            # Matikan thinking agar output tidak habis ke reasoning tokens
            'thinkingConfig': {'thinkingBudget': 0},
        },
    }
    try:
        r = requests.post(
            url,
            params={'key': key},
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        log.warning('Gemini request error: %s', e)
        return None

    if r.status_code != 200:
        log.warning('Gemini HTTP %s: %s', r.status_code, r.text[:300])
        return None

    try:
        data = r.json()
        parts = data['candidates'][0]['content']['parts']
        text = ''.join(p.get('text', '') for p in parts)
    except (KeyError, IndexError, TypeError) as e:
        log.warning('Gemini parse fail: %s — body=%s', e, r.text[:300])
        return None

    guess = _normalize(text)
    if guess:
        log.info('Gemini guess=%s (raw=%r model=%s)', guess, text.strip()[:40], mdl)
    else:
        log.warning('Gemini unusable raw=%r', text.strip()[:80])
    return guess
