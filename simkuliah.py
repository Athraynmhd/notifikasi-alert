"""Klien HTTP SIMKULIAH: login otomatis + session reuse.

PENTING: server meregenerasi CAPTCHA setelah jawaban salah →
satu tebakan terbaik per attempt (bukan multi-candidate).
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import requests

import captcha_utils as cu
import solver_ocr
from config import (
    BASE_URL,
    REQUEST_TIMEOUT,
    LOGIN_MAX_TRIES,
    LOGIN_RETRY_DELAY,
)

log = logging.getLogger(__name__)


class SIMKULIAH:
    """HTTP client untuk SIMKULIAH dengan auto-login."""

    def __init__(self, base_url: str = BASE_URL):
        self.base = base_url
        self.session: requests.Session | None = None
        self._ultimate = None

    def _solver(self):
        if self._ultimate is None:
            try:
                from char_solver import get_solver
                self._ultimate = get_solver()
            except Exception as e:
                log.warning('UltimateSolver unavailable (%s) — OCR only', e)
                self._ultimate = False
        return self._ultimate if self._ultimate is not False else None

    def _new(self):
        self.session = cu.new_session()
        png = cu.fetch_captcha(self.session, base=self.base)
        return cu.read_rgb(png)

    def best_captcha(self, img) -> Optional[str]:
        """Satu tebakan terbaik via UltimateSolver (glyph+font+kNN+OCR)."""
        s = self._solver()
        if s is not None:
            try:
                g = s.best_guess(img)
                if g:
                    return g
            except Exception as e:
                log.debug('ultimate fail: %s', e)
        return solver_ocr.best_guess(img)

    def _post_login(self, username: str, password: str, guess: str) -> Tuple[str, str]:
        try:
            r = self.session.post(
                self.base + '/login/auth',
                data={
                    'username': username,
                    'password': password,
                    'captcha_answer': guess,
                },
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.ConnectionError as e:
            return 'ERROR', f'koneksi gagal saat login: {e}'
        except requests.Timeout:
            return 'ERROR', 'timeout saat login POST'

        if any(x in r.url for x in ('/absensi', '/dashboard', '/main')):
            return 'LOGIN_OK', f'captcha={guess}'
        if 'Username atau Password' in r.text:
            return 'BAD_CREDS', f'captcha OK ({guess}); kredensial salah'
        return 'WRONG_CAPTCHA', f'captcha={guess}'

    def login_attempt(self, username: str, password: str) -> Tuple[str, str]:
        """Satu sesi = satu tebakan terbaik (consume-on-wrong)."""
        try:
            a = self._new()
        except requests.ConnectionError as e:
            return 'ERROR', f'koneksi gagal: {e}'
        except requests.Timeout:
            return 'ERROR', 'timeout saat fetch captcha'

        guess = self.best_captcha(a)
        if not guess:
            return 'ERROR', 'captcha unreadable (no 5-char candidate)'
        return self._post_login(username, password, guess)

    def login(
        self,
        username: str,
        password: str,
        max_tries: int = LOGIN_MAX_TRIES,
    ) -> bool:
        delay = LOGIN_RETRY_DELAY
        for i in range(1, max_tries + 1):
            kind, msg = self.login_attempt(username, password)
            log.info('  [try %d/%d] %s: %s', i, max_tries, kind, msg)
            if kind == 'LOGIN_OK':
                return True
            if kind == 'BAD_CREDS':
                return False
            time.sleep(min(delay, 5.0))
            delay *= 1.5

        log.warning('Login gagal setelah %d percobaan', max_tries)
        return False

    def logged_in(self) -> bool:
        if not self.session:
            return False
        try:
            r = self.session.get(
                self.base + '/absensi',
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
        except (requests.ConnectionError, requests.Timeout):
            return False
        if r.status_code != 200:
            return False
        url = (r.url or '').lower()
        if '/login' in url:
            return False
        if 'captcha_answer' in r.text or 'name="username"' in r.text.lower():
            return False
        return True

    def ensure_login(
        self,
        username: str,
        password: str,
        max_tries: int = LOGIN_MAX_TRIES,
    ) -> bool:
        if self.logged_in():
            log.debug('Session masih valid — skip login')
            return True
        return self.login(username, password, max_tries=max_tries)

    def get(self, path: str) -> requests.Response:
        if not self.session:
            self.session = requests.Session()
        return self.session.get(self.base + path, timeout=REQUEST_TIMEOUT)
