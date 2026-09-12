"""Notifikasi Telegram — template bersih & mudah dibaca."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Sequence

import requests

log = logging.getLogger(__name__)

API = 'https://api.telegram.org/bot{token}/sendMessage'


def env_token() -> str:
    return os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()


def env_chat_id() -> str:
    return os.environ.get('TELEGRAM_CHAT_ID', '').strip()


def send_message(
    text: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: float = 15.0,
) -> bool:
    token = (token or env_token()).strip()
    chat_id = (chat_id or env_chat_id()).strip()
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            API.format(token=token),
            json={
                'chat_id': chat_id,
                'text': text,
                'disable_web_page_preview': True,
            },
            timeout=timeout,
        )
        if r.status_code != 200 or not r.json().get('ok'):
            log.warning('Telegram gagal: %s %s', r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as e:
        log.warning('Telegram error: %s', e)
        return False


def _jam(s) -> str:
    return (getattr(s, 'jam', '') or '—').replace(' - ', '–')


def format_absensi(
    state: str,
    detail: str,
    *,
    changed: bool = False,
    sesi: Optional[Sequence] = None,
    mahasiswa: str = '',
) -> str:
    from jadwal import today_label, ringkas_status

    sesi = sorted(list(sesi or []), key=lambda x: getattr(x, 'jam_mulai_menit', 0))
    tgl = today_label()
    jam_cek = time.strftime('%H:%M')

    # Header singkat
    if state == 'OPEN':
        head = '🟢 Absen sudah dibuka'
        sub = 'Silakan absen sekarang'
    elif state == 'NOT_OPEN':
        head = '🔴 Absen belum dibuka'
        sub = 'Menunggu dosen / jadwal'
    else:
        head = '⚪ Status tidak jelas'
        sub = (detail or 'Cek SIMKULIAH')[:80]

    if changed:
        head = '⚡ ' + head

    out = [head, sub, f'{tgl} · {jam_cek}']
    if mahasiswa:
        out.append(mahasiswa)
    out.append('')

    if not sesi:
        out.append('Hari ini tidak ada kuliah.')
        return '\n'.join(out)

    r = ringkas_status(sesi)
    summary_bits = []
    if r['HIJAU']:
        summary_bits.append(f"{r['HIJAU']} sudah absen")
    if r['MERAH']:
        summary_bits.append(f"{r['MERAH']} belum absen")
    if r['KUNING']:
        summary_bits.append(f"{r['KUNING']} menunggu")
    out.append(f"Jadwal hari ini ({len(sesi)})")
    if summary_bits:
        out.append(' · '.join(summary_bits))
    out.append('')

    for i, s in enumerate(sesi, 1):
        icon = getattr(s, 'status_icon', '⚪') or '⚪'
        status = getattr(s, 'status_absen', 'Tidak diketahui')
        # singkatkan status
        if 'Sudah' in status:
            status = 'Sudah absen'
        elif 'Belum absen' in status:
            status = 'Belum absen'
        elif 'Belum dilaksanakan' in status:
            status = 'Belum mulai'

        mk = s.mata_kuliah
        if len(mk) > 42:
            mk = mk[:40] + '…'

        block = [
            f'{i}. {mk}',
            f'   {_jam(s)}' + (f' · {s.ruang}' if s.ruang else ''),
        ]
        if s.dosen:
            block.append(f'   {s.dosen}')
        block.append(f'   {icon} {status}')
        out.append('\n'.join(block))
        if i < len(sesi):
            out.append('')

    return '\n'.join(out)
