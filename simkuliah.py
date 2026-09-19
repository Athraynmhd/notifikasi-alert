"""Klien HTTP SIMKULIAH: login otomatis + session reuse.

PENTING: server meregenerasi CAPTCHA setelah jawaban salah →
satu tebakan terbaik per attempt (bukan multi-candidate).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional, Tuple

import requests
from requests.utils import cookiejar_from_dict, dict_from_cookiejar

import captcha_utils as cu
import solver_ocr
from config import (
    BASE_URL,
    REQUEST_TIMEOUT,
    LOGIN_MAX_TRIES,
    LOGIN_RETRY_DELAY,
    USER_AGENT,
    CAPTCHA_SOLVER,
    GEMINI_API_KEY,
)

log = logging.getLogger(__name__)


class SIMKULIAH:
    """HTTP client untuk SIMKULIAH dengan auto-login."""

    def __init__(self, base_url: str = BASE_URL):
        self.base = base_url
        self.session: requests.Session | None = None
        self._ultimate = None
        self._last_captcha_png: bytes | None = None
        # Diisi oleh login() / ensure_login() untuk observability CI
        self.last_login_stats: dict = {
            'attempts': 0,
            'wrong_captcha': 0,
            'errors': 0,
            'used_cookies': False,
            'result': '',
            'solver': CAPTCHA_SOLVER,
        }

    def _solver(self):
        if self._ultimate is None:
            try:
                from char_solver import get_solver
                self._ultimate = get_solver()
            except Exception as e:
                log.warning('UltimateSolver unavailable (%s) — OCR only', e)
                self._ultimate = False
        return self._ultimate if self._ultimate is not False else None

    def _ensure_session(self) -> requests.Session:
        if self.session is None:
            self.session = cu.new_session()
        return self.session

    def save_cookies(self, path: str) -> None:
        """Simpan cookie session ke file (untuk reuse antar CI run)."""
        if not self.session:
            return
        data = {
            'cookies': dict_from_cookiejar(self.session.cookies),
            'saved_at': time.time(),
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def load_cookies(self, path: str) -> bool:
        """Muat cookie dari file. Return True jika file ada & terisi."""
        if not os.path.exists(path):
            return False
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            cookies = data.get('cookies') or {}
            if not cookies:
                return False
            s = self._ensure_session()
            s.cookies = cookiejar_from_dict(cookies)
            s.headers.update({'User-Agent': USER_AGENT})
            age = time.time() - float(data.get('saved_at') or 0)
            log.info('Cookie dimuat dari %s (umur %.0f menit)', path, age / 60)
            return True
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            log.warning('Gagal load cookie: %s', e)
            return False

    def _new(self):
        self.session = cu.new_session()
        png = cu.fetch_captcha(self.session, base=self.base)
        self._last_captcha_png = png
        return cu.read_rgb(png)

    def best_captcha(self, img) -> Optional[str]:
        """Satu tebakan terbaik. Default: Gemini Vision, fallback lokal."""
        mode = (CAPTCHA_SOLVER or 'gemini').lower()
        png = self._last_captcha_png

        if mode in ('gemini', 'auto') and png and GEMINI_API_KEY:
            try:
                import solver_gemini
                g = solver_gemini.best_guess(png)
                if g:
                    return g
                log.info('Gemini tidak menghasilkan tebakan — fallback lokal')
            except Exception as e:
                log.warning('Gemini solver error: %s — fallback lokal', e)
            if mode == 'gemini':
                # Tetap fallback lokal agar login tidak macet total
                pass

        if mode in ('local', 'auto', 'gemini'):
            s = self._solver()
            if s is not None:
                try:
                    g = s.best_guess(img)
                    if g:
                        return g
                except Exception as e:
                    log.debug('ultimate fail: %s', e)
            return solver_ocr.best_guess(img)
        return None

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
        stats = {
            'attempts': 0,
            'wrong_captcha': 0,
            'errors': 0,
            'used_cookies': False,
            'result': '',
        }
        for i in range(1, max_tries + 1):
            kind, msg = self.login_attempt(username, password)
            stats['attempts'] = i
            log.info('  [try %d/%d] %s: %s', i, max_tries, kind, msg)
            if kind == 'LOGIN_OK':
                stats['result'] = 'LOGIN_OK'
                self.last_login_stats = stats
                return True
            if kind == 'BAD_CREDS':
                stats['result'] = 'BAD_CREDS'
                self.last_login_stats = stats
                return False
            if kind == 'WRONG_CAPTCHA':
                stats['wrong_captcha'] += 1
            else:
                stats['errors'] += 1
            time.sleep(min(delay, 5.0))
            delay *= 1.5

        log.warning('Login gagal setelah %d percobaan', max_tries)
        stats['result'] = 'MAX_TRIES'
        self.last_login_stats = stats
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
        cookies_path: str | None = None,
    ) -> bool:
        """Reuse cookie jika masih valid; login+CAPTCHA hanya jika perlu."""
        loaded = False
        if cookies_path:
            loaded = self.load_cookies(cookies_path)
        if self.logged_in():
            log.info('Session masih valid — skip login/CAPTCHA')
            self.last_login_stats = {
                'attempts': 0,
                'wrong_captcha': 0,
                'errors': 0,
                'used_cookies': loaded,
                'result': 'COOKIE_OK',
            }
            if cookies_path:
                self.save_cookies(cookies_path)
            return True
        log.info('Session kosong/expired — login ulang')
        ok = self.login(username, password, max_tries=max_tries)
        self.last_login_stats['used_cookies'] = False
        if ok and cookies_path:
            self.save_cookies(cookies_path)
        return ok

    def do_absen(self) -> tuple[bool, str]:
        """Submit absensi dari halaman /absensi. Return (success, message)."""
        if not self.session:
            return False, 'No session'
        try:
            r = self.session.get(self.base + '/absensi', timeout=REQUEST_TIMEOUT, allow_redirects=True)
        except (requests.ConnectionError, requests.Timeout) as e:
            return False, f'Gagal fetch /absensi: {e}'

        import re

        def _abs_url(u: str) -> str:
            if u.startswith('http'):
                return u
            return self.base + ('/' + u.lstrip('/') if not u.startswith('/') else u)

        def _verify_absen() -> tuple[bool, str]:
            """Re-fetch /absensi dan cek apakah status berubah ke hijau."""
            try:
                v = self.session.get(self.base + '/absensi', timeout=REQUEST_TIMEOUT, allow_redirects=True)
                from tool import state_of
                st, _ = state_of(v.text)
                if st == 'NOT_OPEN':
                    return True, 'Absensi tercatat (status: NOT_OPEN / sudah absen)'
                if 'sudah' in v.text.lower() and 'absen' in v.text.lower():
                    return True, 'Absensi tercatat (terdeteksi "sudah absen")'
                return False, f'Status setelah submit: {st} — mungkin belum tercatat'
            except Exception as e:
                return False, f'Gagal verifikasi: {e}'

        # Coba form action dulu
        fm = re.search(r'(<form[^>]*action="([^"]*do_absen[^"]*)"[^>]*>.*?</form>)', r.text, re.I | re.S)
        if fm:
            form_html = fm.group(1)
            url = _abs_url(fm.group(2))
            hidden = dict(re.findall(
                r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form_html,
            ))
            try:
                resp = self.session.post(url, data=hidden, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                if resp.status_code != 200:
                    return False, f'HTTP {resp.status_code} dari {url}'
                return _verify_absen()
            except (requests.ConnectionError, requests.Timeout) as e:
                return False, f'Gagal POST absen: {e}'

        # Fallback: link/button href do_absen
        lm = re.search(r'href="([^"]*do_absen[^"]*)"', r.text, re.I)
        if not lm:
            bm = re.search(r'btn-absen[^>]*(?:href|action)="([^"]+)"', r.text, re.I)
            if not bm:
                return False, 'Tombol/form absen tidak ditemukan di halaman'
            lm = bm

        url = _abs_url(lm.group(1))
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                return False, f'HTTP {resp.status_code} dari {url}'
            return _verify_absen()
        except (requests.ConnectionError, requests.Timeout) as e:
            return False, f'Gagal request absen: {e}'

    def get(self, path: str) -> requests.Response:
        if not self.session:
            self.session = requests.Session()
        return self.session.get(self.base + path, timeout=REQUEST_TIMEOUT)
