"""Notifikasi Telegram — template sesuai desain user."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Sequence

import requests

log = logging.getLogger(__name__)

API = 'https://api.telegram.org/bot{token}/{method}'

BULAN = (
    '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
)

HARI = {
    0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis',
    4: 'Jumat', 5: 'Sabtu', 6: 'Minggu',
}

LINK = 'https://simkuliah.usk.ac.id/index.php/absensi'


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
            API.format(token=token, method='sendMessage'),
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


def tanggal_indonesia() -> str:
    from jadwal import _now
    n = _now()
    return f'{HARI[n.weekday()]}, {n.day} {BULAN[n.month]} {n.year}'


def _jam(s) -> str:
    return (getattr(s, 'jam', '') or '—').replace(' - ', '–')


def _status_label(s) -> tuple[str, str]:
    """Return (icon, short text)."""
    status = getattr(s, 'status_absen', '') or ''
    icon = getattr(s, 'status_icon', '⚪') or '⚪'
    if 'Sudah' in status:
        return icon, 'Sudah absen'
    if 'Belum absen' in status or 'bermasalah' in status.lower():
        return '🔴', 'Belum absen'
    if 'Belum dilaksanakan' in status or 'menunggu' in status.lower():
        return '🟡', 'Belum mulai'
    return icon, status or 'Tidak diketahui'


def _mk_title(name: str, limit: int = 48) -> str:
    name = (name or '').strip()
    if len(name) <= limit:
        return name
    return name[: limit - 1] + '…'


def _blok_list(s, no: int) -> str:
    icon, st = _status_label(s)
    lines = [f'{no}. {_mk_title(s.mata_kuliah)}']
    meta = f'🕐 {_jam(s)}'
    if s.ruang:
        meta += f' · 📍 {s.ruang}'
    lines.append(meta)
    if s.dosen:
        lines.append(f'👨‍🏫 {s.dosen}')
    lines.append(f'{icon} {st}')
    return '\n'.join(lines)


def _blok_detail(s) -> str:
    """Kartu detail (untuk ABSENSI SUDAH DIBUKA, satu/lebih sesi)."""
    lines = [f'📚 {_mk_title(s.mata_kuliah, 60)}', '']
    lines.append(f'🕐 {_jam(s)}')
    if s.ruang:
        lines.append(f'📍 {s.ruang}')
    if s.dosen:
        lines.append(f'👨‍🏫 {s.dosen}')
    tags = []
    if s.kode:
        tags.append(s.kode)
    if s.kelas:
        tags.append(f'Kelas {s.kelas}')
    if s.sks:
        tags.append(f'{s.sks} SKS')
    if tags:
        lines.append('')
        lines.append(f'🏷️ {" · ".join(tags)}')
    if s.pertemuan:
        lines.append(f'📖 Pertemuan ke-{s.pertemuan}')
    icon, st = _status_label(s)
    lines.append('')
    lines.append(f'{icon} {st}')
    return '\n'.join(lines)


def format_absensi(
    state: str,
    detail: str,
    *,
    changed: bool = False,
    sesi: Optional[Sequence] = None,
    mahasiswa: str = '',
) -> str:
    from jadwal import ringkas_status

    sesi = sorted(list(sesi or []), key=lambda x: getattr(x, 'jam_mulai_menit', 0))
    tgl = tanggal_indonesia()
    jam_cek = time.strftime('%H:%M')
    jam_detik = time.strftime('%H:%M:%S')

    if state == 'OPEN':
        lines = [
            '🟢 ABSENSI SUDAH DIBUKA',
            '',
            'Dosen telah membuka absensi.',
            '⚡ Segera lakukan absensi di SIMKULIAH.',
            '',
            f'📅 {tgl}',
            f'🕐 Terdeteksi {jam_detik}',
        ]
        if mahasiswa:
            lines += ['', f'👤 {mahasiswa}']
        if not sesi:
            lines += ['', '📭 Tidak ada mata kuliah terjadwal hari ini.']
        elif len(sesi) == 1:
            lines += ['', _blok_detail(sesi[0])]
        else:
            r = ringkas_status(sesi)
            lines += [
                '',
                f'📚 Jadwal hari ini — {len(sesi)} mata kuliah',
            ]
            bits = []
            if r['HIJAU']:
                bits.append(f"🟢 {r['HIJAU']} sudah absen")
            if r['MERAH']:
                bits.append(f"🔴 {r['MERAH']} belum absen")
            if r['KUNING']:
                bits.append(f"🟡 {r['KUNING']} menunggu")
            if bits:
                lines.append(' · '.join(bits))
            lines.append('')
            for i, s in enumerate(sesi, 1):
                lines.append(_blok_list(s, i))
                if i < len(sesi):
                    lines.append('')
    else:
        # NOT_OPEN / UNKNOWN
        if state == 'NOT_OPEN':
            title = '🔴 ABSENSI BELUM DIBUKA'
            desc = 'Dosen belum membuka absensi atau belum masuk waktu absen.'
        else:
            title = '⚪ STATUS ABSENSI TIDAK JELAS'
            desc = (detail or 'Periksa halaman absensi secara manual.')[:120]

        lines = [
            title,
            '',
            desc,
            '',
            f'📅 {tgl}',
            f'🕐 Dicek {jam_cek}',
        ]
        if not sesi:
            lines += ['', '📭 Tidak ada mata kuliah terjadwal hari ini.']
        else:
            r = ringkas_status(sesi)
            lines += [
                '',
                f'📚 Jadwal hari ini — {len(sesi)} mata kuliah',
            ]
            bits = []
            if r['HIJAU']:
                bits.append(f"🟢 {r['HIJAU']} sudah absen")
            if r['MERAH']:
                bits.append(f"🔴 {r['MERAH']} belum absen")
            if r['KUNING']:
                bits.append(f"🟡 {r['KUNING']} menunggu")
            if bits:
                lines.append(' · '.join(bits))
            lines.append('')
            for i, s in enumerate(sesi, 1):
                lines.append(_blok_list(s, i))
                if i < len(sesi):
                    lines.append('')

    lines += ['', f'🔗 SIMKULIAH\n{LINK}']
    return '\n'.join(lines)


TG_MAX_LEN = 4096


def _truncate(text: str) -> str:
    if len(text) <= TG_MAX_LEN:
        return text
    return text[:TG_MAX_LEN - 20] + '\n\n[…dipotong]'


def send_absen_prompt(
    text: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: float = 15.0,
) -> Optional[int]:
    """Kirim pesan dengan tombol inline Absen/Tidak. Return message_id atau None."""
    text = _truncate(text)
    token = (token or env_token()).strip()
    chat_id = (chat_id or env_chat_id()).strip()
    if not token or not chat_id:
        return None
    keyboard = {
        'inline_keyboard': [[
            {'text': '✅ Absen Sekarang', 'callback_data': 'do_absen'},
            {'text': '❌ Tidak', 'callback_data': 'skip_absen'},
        ]]
    }
    try:
        r = requests.post(
            API.format(token=token, method='sendMessage'),
            json={
                'chat_id': chat_id,
                'text': text,
                'reply_markup': keyboard,
                'disable_web_page_preview': True,
            },
            timeout=timeout,
        )
        data = r.json()
        if data.get('ok'):
            return data['result']['message_id']
        log.warning('Telegram prompt gagal: %s', r.text[:200])
    except requests.RequestException as e:
        log.warning('Telegram prompt error: %s', e)
    return None


def poll_callback(
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    wait_seconds: int = 90,
    poll_interval: float = 3.0,
) -> Optional[str]:
    """Poll getUpdates untuk callback_query. Return callback_data atau None."""
    token = (token or env_token()).strip()
    chat_id = (chat_id or env_chat_id()).strip()
    if not token:
        return None

    # Flush stale updates agar tidak ambil callback dari prompt sebelumnya
    try:
        r = requests.get(
            API.format(token=token, method='getUpdates'),
            params={'offset': -1, 'limit': 1, 'timeout': 0},
            timeout=10,
        )
        data = r.json()
        results = data.get('result', [])
        offset = (results[-1]['update_id'] + 1) if results else None
    except Exception:
        offset = None

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        remaining = max(1, int(deadline - time.time()))
        try:
            params: dict = {'timeout': min(remaining, 30), 'allowed_updates': '["callback_query"]'}
            if offset is not None:
                params['offset'] = offset
            r = requests.get(
                API.format(token=token, method='getUpdates'),
                params=params,
                timeout=min(remaining, 30) + 10,
            )
            data = r.json()
            for upd in data.get('result', []):
                offset = upd['update_id'] + 1
                cb = upd.get('callback_query')
                if not cb:
                    continue
                cb_chat = str(cb.get('message', {}).get('chat', {}).get('id', ''))
                if chat_id and cb_chat != chat_id:
                    continue
                cb_data = cb.get('data', '')
                # Answer callback to remove loading spinner
                try:
                    requests.post(
                        API.format(token=token, method='answerCallbackQuery'),
                        json={'callback_query_id': cb['id']},
                        timeout=5,
                    )
                except Exception:
                    pass
                if cb_data in ('do_absen', 'skip_absen'):
                    return cb_data
        except requests.RequestException as e:
            log.debug('poll error: %s', e)
            time.sleep(poll_interval)
    return None


def edit_message(
    message_id: int,
    text: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """Edit pesan yang sudah dikirim (hapus tombol, update teks)."""
    text = _truncate(text)
    token = (token or env_token()).strip()
    chat_id = (chat_id or env_chat_id()).strip()
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            API.format(token=token, method='editMessageText'),
            json={
                'chat_id': chat_id,
                'message_id': message_id,
                'text': text,
                'disable_web_page_preview': True,
            },
            timeout=10,
        )
        return r.json().get('ok', False)
    except requests.RequestException:
        return False
