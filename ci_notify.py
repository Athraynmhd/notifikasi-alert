"""CI entry: cek absensi + kirim Telegram hanya jika status berubah.

Production features:
- ABSEN_MODE: confirm | auto | notify_only
- Metrik login/CAPTCHA + streak di .ci_state.json
- Alert login gagal beruntun (tanpa spam tiap 5 menit)
- Alert parser UNKNOWN (kemungkinan HTML drift)
"""

from __future__ import annotations

import json
import logging
import os
import sys

import absen_flow
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


def main() -> int:
    setup_logging()
    user = os.environ.get('SIMKULIAH_USER', '').strip()
    password = os.environ.get('SIMKULIAH_PASS', '').strip()
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    force = os.environ.get('NOTIFY_FORCE', '').strip() in ('1', 'true', 'yes')
    mode = absen_flow.get_absen_mode()

    if not user or not password:
        log.error('SIMKULIAH_USER / SIMKULIAH_PASS wajib di Secrets')
        return 2
    if not token or not chat:
        log.error('TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID wajib di Secrets')
        return 2

    os.environ.setdefault('TESSERACT_PATH', '/usr/bin/tesseract')
    prev = load_state()

    c = simkuliah.SIMKULIAH()
    ok = c.ensure_login(
        user,
        password,
        max_tries=int(os.environ.get('LOGIN_MAX_TRIES', '15')),
        cookies_path=COOKIES_PATH,
    )
    stats = dict(c.last_login_stats or {})

    if not ok:
        metrics = absen_flow.merge_metrics(
            prev, login_ok=False, login_stats=stats, state='LOGIN_FAIL',
        )
        streak = int(metrics['login_fail_streak'])
        if absen_flow.should_alert_login_fail(prev, streak):
            tg.send_message(
                absen_flow.format_login_fail_alert(streak, stats),
                token=token, chat_id=chat,
            )
        else:
            log.info('Login gagal streak=%d — skip alert (throttle)', streak)
        save_state({
            **{k: prev.get(k) for k in ('fingerprint', 'state', 'sesi', 'in_window')},
            **metrics,
        })
        return 1

    info = report(c, show_pages=False)
    a = info['absensi']
    sesi = info.get('_sesi_obj') or []
    fp = absen_flow.fingerprint(info)
    changed = force or (prev.get('fingerprint') != fp)

    in_window = jadwal.dalam_jendela_kuliah(sesi, buffer_menit=BUFFER_MENIT)
    no_class_today = len(sesi) == 0
    allow_notify = force or in_window or no_class_today

    metrics = absen_flow.merge_metrics(
        prev, login_ok=True, login_stats=stats, state=a.get('state', ''),
    )

    log.info(
        'state=%s mode=%s sesi=%d changed=%s in_window=%s login=%s',
        a.get('state'), mode, len(sesi), changed, in_window,
        stats.get('result'),
    )

    # Parser drift: UNKNOWN di jendela kuliah / transisi ke UNKNOWN
    if absen_flow.should_alert_parser_unknown(prev, a.get('state', ''), in_window=in_window):
        tg.send_message(
            absen_flow.format_parser_unknown_alert(
                a.get('detail', ''), int(metrics['parser_unknown_streak']),
            ),
            token=token, chat_id=chat,
        )

    exit_code = 0
    if changed and allow_notify:
        msg = tg.format_absensi(
            a['state'], a.get('detail', ''),
            changed=bool(prev.get('fingerprint')),
            sesi=sesi,
            mahasiswa=a.get('mahasiswa', ''),
        )

        if a.get('state') == 'OPEN' and absen_flow.ada_belum_absen(sesi):
            exit_code = absen_flow.handle_open_absen(
                c,
                msg=msg,
                user=user,
                password=password,
                cookies_path=COOKIES_PATH,
                token=token,
                chat_id=chat,
                mode=mode,
            )
        else:
            if not tg.send_message(msg, token=token, chat_id=chat):
                log.error('Gagal kirim Telegram')
                exit_code = 1
            else:
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
        **metrics,
    })
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
