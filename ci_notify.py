"""CI entry: cek absensi + kirim Telegram hanya jika status berubah.

- Cron tiap 3 menit
- Fokus di jendela jam kuliah (±15 menit sebelum mulai s/d selesai)
- Tidak spam: hanya saat fingerprint berubah
"""

from __future__ import annotations

import json
import logging
import os
import sys

import jadwal
import simkuliah
import telegram_notify as tg
from config import setup_logging
from tool import report

log = logging.getLogger(__name__)

STATE_PATH = os.environ.get('ABSEN_STATE_PATH', '.ci_state.json')
COOKIES_PATH = os.environ.get('ABSEN_COOKIES_PATH', '.ci_cookies.json')
BUFFER_MENIT = int(os.environ.get('CLASS_BUFFER_MINUTES', '15'))


def load_state() -> dict:
    try:
        with open(STATE_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(data: dict) -> None:
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fingerprint(info: dict) -> str:
    a = info.get('absensi', {})
    jadwal_list = info.get('jadwal_hari_ini', [])
    parts = [
        a.get('state', ''),
        *(
            f"{j.get('kode')}|{j.get('warna')}|{j.get('jam')}|{j.get('status_absen')}"
            for j in jadwal_list
        ),
    ]
    return '||'.join(parts)


def main() -> int:
    setup_logging()
    user = os.environ.get('SIMKULIAH_USER', '').strip()
    password = os.environ.get('SIMKULIAH_PASS', '').strip()
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    force = os.environ.get('NOTIFY_FORCE', '').strip() in ('1', 'true', 'yes')

    if not user or not password:
        log.error('SIMKULIAH_USER / SIMKULIAH_PASS wajib di Secrets')
        return 2
    if not token or not chat:
        log.error('TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID wajib di Secrets')
        return 2

    os.environ.setdefault('TESSERACT_PATH', '/usr/bin/tesseract')

    c = simkuliah.SIMKULIAH()
    ok = c.ensure_login(
        user,
        password,
        max_tries=int(os.environ.get('LOGIN_MAX_TRIES', '15')),
        cookies_path=COOKIES_PATH,
    )
    if not ok:
        tg.send_message(
            '⚠️ SIMKULIAH login gagal (CI). Cek kredensial / CAPTCHA.',
            token=token, chat_id=chat,
        )
        return 1

    info = report(c, show_pages=False)
    a = info['absensi']
    sesi = info.get('_sesi_obj') or []
    fp = fingerprint(info)
    prev = load_state()
    changed = force or (prev.get('fingerprint') != fp)

    in_window = jadwal.dalam_jendela_kuliah(sesi, buffer_menit=BUFFER_MENIT)
    # Tidak ada kuliah hari ini: boleh kirim 1x (fingerprint), lalu diam
    no_class_today = len(sesi) == 0
    allow_notify = force or in_window or no_class_today

    log.info(
        'state=%s sesi=%d changed=%s in_window=%s',
        a.get('state'), len(sesi), changed, in_window,
    )

    if changed and allow_notify:
        msg = tg.format_absensi(
            a['state'], a.get('detail', ''),
            changed=bool(prev.get('fingerprint')),
            sesi=sesi,
            mahasiswa=a.get('mahasiswa', ''),
        )
        if not tg.send_message(msg, token=token, chat_id=chat):
            log.error('Gagal kirim Telegram')
            return 1
        log.info('Telegram terkirim')
    elif changed and not allow_notify:
        log.info('Ada perubahan tapi di luar jam kuliah — simpan state, skip Telegram')
    else:
        log.info('Tidak ada perubahan — skip notifikasi')

    save_state({
        'fingerprint': fp,
        'state': a.get('state'),
        'sesi': len(sesi),
        'in_window': in_window,
    })
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
