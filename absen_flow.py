"""Orchestration production: mode absen, metrics, alert, fingerprint.

Dipakai oleh ci_notify (dan bisa dipakai monitor lokal).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional, Sequence

import simkuliah
import telegram_notify as tg
from config import (
    ABSEN_MODE_DEFAULT,
    ABSEN_MODES,
    LOGIN_FAIL_ALERT_EVERY,
    PARSER_UNKNOWN_ALERT,
)

log = logging.getLogger(__name__)


def get_absen_mode(raw: Optional[str] = None) -> str:
    m = (raw if raw is not None else os.environ.get('ABSEN_MODE', ABSEN_MODE_DEFAULT))
    m = (m or ABSEN_MODE_DEFAULT).strip().lower()
    if m not in ABSEN_MODES:
        log.warning('ABSEN_MODE=%r tidak dikenal — pakai %s', m, ABSEN_MODE_DEFAULT)
        return ABSEN_MODE_DEFAULT
    return m


def fingerprint(info: dict) -> str:
    a = info.get('absensi', {})
    jadwal_list = info.get('jadwal_hari_ini', [])
    sesi_page = a.get('sesi_page') or []
    parts = [
        a.get('state', ''),
        a.get('batas_reason', ''),
        *(
            f"{j.get('kode')}|{j.get('warna')}|{j.get('jam')}|{j.get('status_absen')}"
            for j in jadwal_list
        ),
        *(
            f"B|{s.get('jam')}|{s.get('batas_text')}|{int(bool(s.get('sudah_absen')))}"
            for s in sesi_page
        ),
    ]
    return '||'.join(parts)


def ada_belum_absen(sesi: Sequence) -> bool:
    return any(getattr(s, 'warna', '') == 'MERAH' for s in sesi)


def should_alert_login_fail(prev: dict, streak: int) -> bool:
    """Alert pada gagal pertama, lalu tiap LOGIN_FAIL_ALERT_EVERY."""
    if streak <= 0:
        return False
    every = max(1, LOGIN_FAIL_ALERT_EVERY)
    if streak == 1:
        return True
    return streak % every == 0


def should_alert_parser_unknown(prev: dict, state: str, *, in_window: bool) -> bool:
    if not PARSER_UNKNOWN_ALERT or state != 'UNKNOWN':
        return False
    # Selalu alert saat masuk UNKNOWN pertama kali, atau di jendela kuliah
    if prev.get('state') != 'UNKNOWN':
        return True
    return in_window


def merge_metrics(prev: dict, *, login_ok: bool, login_stats: Optional[dict], state: str) -> dict:
    """Update streak & ringkasan metrik untuk disimpan di state file."""
    fail_streak = int(prev.get('login_fail_streak') or 0)
    unknown_streak = int(prev.get('parser_unknown_streak') or 0)

    if login_ok:
        fail_streak = 0
    else:
        fail_streak += 1

    if state == 'UNKNOWN':
        unknown_streak += 1
    else:
        unknown_streak = 0

    metrics: dict[str, Any] = {
        'login_fail_streak': fail_streak,
        'parser_unknown_streak': unknown_streak,
        'last_run_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'last_login_ok': login_ok,
        'absen_mode': get_absen_mode(),
    }
    if login_stats:
        metrics['last_login'] = {
            'attempts': login_stats.get('attempts', 0),
            'wrong_captcha': login_stats.get('wrong_captcha', 0),
            'errors': login_stats.get('errors', 0),
            'used_cookies': bool(login_stats.get('used_cookies')),
            'result': login_stats.get('result', ''),
        }
    return metrics


def format_login_fail_alert(streak: int, stats: Optional[dict] = None) -> str:
    lines = [
        '⚠️ SIMKULIAH login gagal (CI)',
        f'Streak gagal: {streak}x berturut-turut',
        'Cek kredensial / CAPTCHA / jaringan.',
    ]
    if stats:
        lines.append(
            f"Attempts: {stats.get('attempts', '?')} · "
            f"Wrong CAPTCHA: {stats.get('wrong_captcha', '?')} · "
            f"Errors: {stats.get('errors', '?')}"
        )
        if stats.get('result'):
            lines.append(f"Result: {stats['result']}")
    return '\n'.join(lines)


def format_parser_unknown_alert(detail: str, streak: int) -> str:
    return (
        '⚪ Parser absensi: STATUS UNKNOWN\n'
        f'Streak: {streak}x\n'
        'Kemungkinan HTML SIMKULIAH berubah — cek fixture/test & dump /absensi.\n'
        f'Detail: {(detail or "")[:160]}'
    )


def run_absen(
    client: simkuliah.SIMKULIAH,
    *,
    user: str,
    password: str,
    cookies_path: str,
) -> tuple[bool, str]:
    """Pastikan session valid lalu submit absensi."""
    if not client.logged_in():
        log.info('Session expired — re-login sebelum absen')
        ok = client.ensure_login(user, password, cookies_path=cookies_path)
        if not ok:
            return False, 'Re-login gagal sebelum absen'
    return client.do_absen()


def handle_open_absen(
    client: simkuliah.SIMKULIAH,
    *,
    msg: str,
    user: str,
    password: str,
    cookies_path: str,
    token: str,
    chat_id: str,
    mode: Optional[str] = None,
) -> int:
    """Tangani OPEN + ada MERAH sesuai ABSEN_MODE.

    Return 0 sukses jalur notify/absen, 1 gagal kirim Telegram kritis.
    """
    mode = get_absen_mode(mode)

    if mode == 'notify_only':
        note = msg + '\n\nℹ️ Mode NOTIFY_ONLY — absen manual di SIMKULIAH.'
        if not tg.send_message(note, token=token, chat_id=chat_id):
            log.error('Gagal kirim Telegram (notify_only)')
            return 1
        log.info('Telegram terkirim (notify_only)')
        return 0

    if mode == 'auto':
        log.info('Mode AUTO — absen langsung')
        ok_absen, absen_msg = run_absen(
            client, user=user, password=password, cookies_path=cookies_path,
        )
        if ok_absen:
            result = f'✅ Absensi otomatis berhasil!\n\n{absen_msg}'
        else:
            result = f'⚠️ Absensi otomatis gagal: {absen_msg}'
        body = msg + f'\n\n🤖 Mode AUTO\n{result}'
        if not tg.send_message(body, token=token, chat_id=chat_id):
            log.error('Gagal kirim Telegram (auto)')
            return 1
        log.info('Absensi AUTO: %s — %s', 'OK' if ok_absen else 'GAGAL', absen_msg)
        return 0

    # confirm
    prompt = msg + '\n\n❓ Apakah Anda mau absen sekarang?'
    wait_sec = int(os.environ.get('ABSEN_WAIT_SECONDS', '90'))
    msg_id = tg.send_absen_prompt(prompt, token=token, chat_id=chat_id)
    if not msg_id:
        log.error('Gagal kirim prompt Telegram')
        return 1

    log.info('Menunggu respon Telegram (%d detik)...', wait_sec)
    choice = tg.poll_callback(token=token, chat_id=chat_id, wait_seconds=wait_sec)
    if choice == 'do_absen':
        log.info('User memilih ABSEN — menjalankan absensi...')
        ok_absen, absen_msg = run_absen(
            client, user=user, password=password, cookies_path=cookies_path,
        )
        if ok_absen:
            result = f'✅ Absensi berhasil!\n\n{absen_msg}'
        else:
            result = f'⚠️ Absensi gagal: {absen_msg}'
        tg.edit_message(msg_id, prompt + f'\n\n{result}', token=token, chat_id=chat_id)
        log.info('Absensi: %s — %s', 'OK' if ok_absen else 'GAGAL', absen_msg)
    elif choice == 'skip_absen':
        tg.edit_message(msg_id, prompt + '\n\n⏭️ Absen dilewati.', token=token, chat_id=chat_id)
        log.info('User memilih TIDAK absen')
    else:
        tg.edit_message(msg_id, prompt + '\n\n⏰ Tidak ada respon (timeout).', token=token, chat_id=chat_id)
        log.info('Timeout — tidak ada respon dari user')
    return 0
