"""CLI entrypoint: login, status, monitor — + notifikasi Telegram lengkap."""

from __future__ import annotations

import argparse
import html as H
import json
import logging
import os
import re
import signal
import sys
import time

import jadwal
import simkuliah
import telegram_notify as tg
import absensi_meta
from config import setup_logging

log = logging.getLogger(__name__)


def state_of(text: str) -> tuple[str, str]:
    """Classify /absensi. Prioritas: kolom Batas Absen, lalu heuristik lama."""
    sesi = absensi_meta.parse_sesi_absensi(text)
    if sesi:
        st, detail = absensi_meta.state_from_batas(sesi)
        if st != 'UNKNOWN':
            return st, detail

    txt = re.sub(r'<script.*?</script>', ' ', text, flags=re.S)
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = H.unescape(txt)
    txt = ' '.join(txt.split())
    lower = txt.lower()
    if 'belum masuk waktu absen' in lower or 'dosen belum absen' in lower:
        return 'NOT_OPEN', 'Dosen belum absen / belum masuk waktu absen'
    if 'anda sudah absen' in lower and 'btn-absen' not in text.lower() and 'do_absen' not in text.lower():
        return 'NOT_OPEN', 'Anda sudah absen'
    # Tombol saja TIDAK cukup (bisa muncul meski dosen belum absen)
    if 'btn-absen' in text.lower() or 'do_absen' in text.lower():
        if 'belum masuk waktu' not in lower and 'dosen belum absen' not in lower:
            return 'OPEN', 'Tombol absen tersedia (fallback tanpa Batas Absen)'
    return 'UNKNOWN', txt[:180]


def extract_mahasiswa(html: str) -> str:
    m = re.search(
        r'<div[^>]*class="[^"]*user-profile[^"]*"[^>]*>.*?<h[^>]*>([^<]+)</h',
        html, re.S | re.I,
    )
    if m:
        return m.group(1).strip()
    # fallback: pola umum di header
    m = re.search(r'Mahasiswa\s*</[^>]+>\s*<[^>]+>([^<]{3,60})</', html, re.I)
    return m.group(1).strip() if m else ''


def report(client: simkuliah.SIMKULIAH, show_pages: bool = True) -> dict:
    """Kumpulkan status absensi + jadwal hari ini + meta Batas Absen."""
    out: dict = {}
    r = client.get('/absensi')
    st, detail = state_of(r.text)
    sesi_page = absensi_meta.parse_sesi_absensi(r.text)
    target, batas_reason = absensi_meta.pilih_sesi_bisa_absen(sesi_page)
    out['absensi'] = {
        'state': st,
        'detail': detail,
        'http': r.status_code,
        'mahasiswa': extract_mahasiswa(r.text),
        'sesi_page': [s.to_dict() for s in sesi_page],
        'batas_reason': batas_reason,
        'batas_aktif': target.to_dict() if target and batas_reason == 'within_batas' else None,
        'batas_expired': target.to_dict() if target and batas_reason == 'expired' else None,
    }
    try:
        sesi = jadwal.fetch_hari_ini(client)
        out['jadwal_hari_ini'] = [
            {
                'kode': s.kode,
                'mata_kuliah': s.mata_kuliah,
                'kelas': s.kelas,
                'sks': s.sks,
                'dosen': s.dosen,
                'jam': s.jam,
                'ruang': s.ruang,
                'pertemuan': s.pertemuan,
                'hari_tanggal': s.hari_tanggal,
                'warna': s.warna,
                'status_absen': s.status_absen,
            }
            for s in sesi
        ]
        out['_sesi_obj'] = sesi
    except Exception as e:
        log.warning('Gagal parse jadwal: %s', e)
        out['jadwal_hari_ini'] = []
        out['_sesi_obj'] = []

    if show_pages:
        for path in ('/jadwal_kuliah/index',
                     '/jadwal_kuliah/jadwal_kuliah_hari_ini',
                     '/jadwal_kuliah/jadwal_kuliah_asisten_lab'):
            rr = client.get(path)
            out[path] = {'http': rr.status_code, 'url': rr.url}
    return out


def _tg_args(args: argparse.Namespace) -> tuple[str, str]:
    token = getattr(args, 'telegram_token', '') or tg.env_token()
    chat = getattr(args, 'telegram_chat', '') or tg.env_chat_id()
    return token, chat


def notify(
    args: argparse.Namespace,
    state: str,
    detail: str,
    *,
    changed: bool,
    sesi=None,
    mahasiswa: str = '',
) -> None:
    token, chat = _tg_args(args)
    if not token or not chat:
        return
    msg = tg.format_absensi(
        state, detail, changed=changed, sesi=sesi or [], mahasiswa=mahasiswa,
    )
    if tg.send_message(msg, token=token, chat_id=chat):
        log.info('Telegram terkirim (%s, %d sesi)', state, len(sesi or []))
    else:
        log.warning('Telegram gagal kirim')


def cmd_login(args: argparse.Namespace) -> None:
    c = simkuliah.SIMKULIAH()
    ok = c.login(args.user, args.password, max_tries=args.max_tries)
    if ok:
        log.info('Login: OK')
    else:
        log.error('Login: GAGAL (kredensial salah/blocked)')


def cmd_status(args: argparse.Namespace) -> None:
    c = simkuliah.SIMKULIAH()
    ok = c.ensure_login(args.user, args.password, max_tries=args.max_tries)
    if not ok:
        log.error('Login GAGAL — kredensial salah?')
        sys.exit(1)

    info = report(c, show_pages=True)
    a = info['absensi']
    sesi = info.get('_sesi_obj') or []
    if args.json:
        dump = {k: v for k, v in info.items() if not k.startswith('_')}
        print(json.dumps(dump, indent=2, ensure_ascii=False))
    else:
        print('=== STATUS ABSENSI ===')
        print(f"absensi          : {a['state']}  (HTTP {a['http']})")
        print(f"detail           : {a['detail']}")
        if a.get('batas_reason'):
            print(f"batas_reason     : {a['batas_reason']}")
        for s in a.get('sesi_page') or []:
            print(
                f"  batas page     : jam={s.get('jam')} batas={s.get('batas_text')} "
                f"sudah={s.get('sudah_absen')} dosen_belum={s.get('dosen_belum_absen')}"
            )
        print(f"jadwal hari ini  : {len(sesi)} sesi (urut jam)")
        for s in sesi:
            print(f"  [{s.warna or '?'}] {s.jam} | {s.mata_kuliah} | {s.status_absen} | {s.dosen}")
        for p in ('/jadwal_kuliah/index', '/jadwal_kuliah/jadwal_kuliah_hari_ini',
                  '/jadwal_kuliah/jadwal_kuliah_asisten_lab'):
            b = info[p]
            print(f"{p:55}: HTTP {b['http']}  -> {b['url']}")

    if getattr(args, 'notify', False):
        notify(
            args, a['state'], a['detail'], changed=False,
            sesi=sesi, mahasiswa=a.get('mahasiswa', ''),
        )


def cmd_monitor(args: argparse.Namespace) -> None:
    c = simkuliah.SIMKULIAH()
    token, chat = _tg_args(args)
    use_tg = bool(token and chat)
    if use_tg:
        log.info('Telegram ON (chat_id=%s)', chat)
    else:
        log.info('Telegram OFF — set TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID')

    log.info('Monitor mulai. Ctrl+C untuk berhenti. Interval %d detik.', args.interval)
    running = True

    def _shutdown(signum, frame):
        nonlocal running
        running = False
        log.info('Sinyal diterima, menghentikan monitor...')

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    last = None
    while running:
        try:
            ok = c.ensure_login(args.user, args.password, max_tries=args.max_tries)
            if not ok:
                log.warning('%s login GAGAL (creds?)', time.strftime('%H:%M:%S'))
                if use_tg:
                    tg.send_message(
                        f'⚠️ SIMKULIAH login gagal ({time.strftime("%H:%M:%S")})',
                        token=token, chat_id=chat,
                    )
            else:
                info = report(c, show_pages=False)
                a = info['absensi']
                sesi = info.get('_sesi_obj') or []
                state = a['state']
                if state != last:
                    log.info('%s [PERUBAHAN] %s — %s (%d sesi hari ini)',
                             time.strftime('%H:%M:%S'), state, a['detail'], len(sesi))
                    if use_tg:
                        notify(
                            args, state, a['detail'],
                            changed=(last is not None),
                            sesi=sesi,
                            mahasiswa=a.get('mahasiswa', ''),
                        )
                    last = state
                else:
                    log.info('%s %s (%d sesi)', time.strftime('%H:%M:%S'), state, len(sesi))
        except Exception as e:
            log.error('%s error: %s', time.strftime('%H:%M:%S'), e)

        for _ in range(args.interval):
            if not running:
                break
            time.sleep(1)

    if use_tg:
        tg.send_message('⏹ Monitor absensi dihentikan.', token=token, chat_id=chat)
    log.info('Monitor dihentikan.')


def cmd_telegram_test(args: argparse.Namespace) -> None:
    token, chat = _tg_args(args)
    if not token or not chat:
        log.error('Butuh TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID')
        sys.exit(2)

    # Preview template tanpa login (contoh)
    from jadwal import SesiKuliah
    contoh = [
        SesiKuliah(
            kode='FPPS1001', mata_kuliah='METODE PENELITIAN', kelas='E', sks='2',
            dosen='Prof. Dr. Hizir', jam='16.35 - 18.15', ruang='E.03.04',
            pertemuan=3, hari_tanggal=jadwal.today_label(),
            tanggal=jadwal.today_str(),
            warna='MERAH', status_absen='Belum absen / bermasalah', status_icon='🔴',
        ),
    ]
    msg_open = tg.format_absensi(
        'OPEN', 'Dosen sudah membuka absen', changed=True,
        sesi=contoh, mahasiswa='Athar Rayyan Muhammad',
    )
    msg_empty = tg.format_absensi(
        'NOT_OPEN', 'Belum waktu', changed=False, sesi=[], mahasiswa='',
    )

    # 1) Status OPEN biasa
    ok1 = tg.send_message(msg_open, token=token, chat_id=chat)
    time.sleep(0.4)
    # 2) Status NOT_OPEN
    ok2 = tg.send_message(msg_empty, token=token, chat_id=chat)
    time.sleep(0.4)
    # 3) Prompt produksi: tombol Absen / Tidak (mode confirm)
    prompt = msg_open + '\n\n❓ Apakah Anda mau absen sekarang?'
    msg_id = tg.send_absen_prompt(prompt, token=token, chat_id=chat)
    ok3 = msg_id is not None

    if ok1 and ok2 and ok3:
        log.info('Tes Telegram: OK (OPEN + NOT_OPEN + prompt tombol Absen/Tidak)')
        log.info('Tekan tombol di chat untuk uji — di tes ini tidak akan absen sungguhan.')
    else:
        log.error('Tes Telegram: GAGAL (open=%s not_open=%s prompt=%s)', ok1, ok2, ok3)
        sys.exit(1)


def cmd_telegram_demo(args: argparse.Namespace) -> None:
    """Simulasi mode confirm: kirim prompt, tunggu tombol, edit balasan (tanpa SIMKULIAH)."""
    token, chat = _tg_args(args)
    if not token or not chat:
        log.error('Butuh TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID')
        sys.exit(2)

    from jadwal import SesiKuliah
    contoh = [
        SesiKuliah(
            kode='FPPS1001', mata_kuliah='METODE PENELITIAN', kelas='E', sks='2',
            dosen='Prof. Dr. Hizir', jam='16.35 - 18.15', ruang='E.03.04',
            pertemuan=3, hari_tanggal=jadwal.today_label(),
            tanggal=jadwal.today_str(),
            warna='MERAH', status_absen='Belum absen / bermasalah', status_icon='🔴',
        ),
    ]
    msg = tg.format_absensi(
        'OPEN', 'Dosen sudah membuka absen', changed=True,
        sesi=contoh, mahasiswa='Athar Rayyan Muhammad',
    )
    prompt = (
        msg
        + '\n\n🧪 DEMO SIMULASI (bukan absen sungguhan)'
        + '\n\n❓ Apakah Anda mau absen sekarang?'
    )
    wait_sec = int(getattr(args, 'wait', 90) or 90)

    msg_id = tg.send_absen_prompt(prompt, token=token, chat_id=chat)
    if not msg_id:
        log.error('Gagal kirim prompt demo')
        sys.exit(1)

    log.info('Prompt terkirim. Tekan tombol di Telegram dalam %d detik...', wait_sec)
    choice = tg.poll_callback(token=token, chat_id=chat, wait_seconds=wait_sec)

    if choice == 'do_absen':
        result = (
            '✅ Absensi berhasil!\n\n'
            'Absensi tercatat (status: NOT_OPEN / sudah absen)\n\n'
            '🧪 Ini hasil DEMO — SIMKULIAH tidak dihubungi.'
        )
        tg.edit_message(msg_id, prompt + f'\n\n{result}', token=token, chat_id=chat)
        log.info('User pilih ABSEN → balasan sukses (demo)')
    elif choice == 'skip_absen':
        tg.edit_message(msg_id, prompt + '\n\n⏭️ Absen dilewati.', token=token, chat_id=chat)
        log.info('User pilih TIDAK → Absen dilewati')
    else:
        tg.edit_message(
            msg_id, prompt + '\n\n⏰ Tidak ada respon (timeout).',
            token=token, chat_id=chat,
        )
        log.info('Timeout — tidak ada tombol yang ditekan')


def main() -> None:
    setup_logging()

    ap = argparse.ArgumentParser(description='SIMKULIAH tool + Telegram notify')
    ap.add_argument(
        'cmd',
        choices=['login', 'status', 'monitor', 'telegram-test', 'telegram-demo'],
    )
    ap.add_argument('--user', default=os.environ.get('SIMKULIAH_USER', ''))
    ap.add_argument('--pass', dest='password', default=os.environ.get('SIMKULIAH_PASS', ''))
    ap.add_argument('--interval', type=int, default=60)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--max-tries', type=int, default=15)
    ap.add_argument('--notify', action='store_true', help='kirim status ke Telegram')
    ap.add_argument('--telegram-token', default=os.environ.get('TELEGRAM_BOT_TOKEN', ''))
    ap.add_argument('--telegram-chat', default=os.environ.get('TELEGRAM_CHAT_ID', ''))
    ap.add_argument('--wait', type=int, default=90, help='detik tunggu tombol (telegram-demo)')
    args = ap.parse_args()

    if args.cmd == 'telegram-test':
        cmd_telegram_test(args)
        return
    if args.cmd == 'telegram-demo':
        cmd_telegram_demo(args)
        return

    if not args.user or not args.password:
        log.error('Silakan beri kredensial: --user <nim> --pass <password>')
        sys.exit(2)

    {'login': cmd_login, 'status': cmd_status, 'monitor': cmd_monitor}[args.cmd](args)


if __name__ == '__main__':
    main()
