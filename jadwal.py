"""Parser jadwal kuliah SIMKULIAH + status warna absen (hijau/merah/kuning)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo('Asia/Jakarta')
except Exception:
    TZ = None

HARI_ID = {
    0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis',
    4: 'Jumat', 5: 'Sabtu', 6: 'Minggu',
}

# Bootstrap table-* di halaman jadwal
WARNA_MAP = {
    'table-success': ('HIJAU', 'Sudah absen', '🟢'),
    'table-danger': ('MERAH', 'Belum absen / bermasalah', '🔴'),
    'table-warning': ('KUNING', 'Belum dilaksanakan', '🟡'),
    'table-info': ('BIRU', 'Info', '🔵'),
    'table-primary': ('BIRU', 'Info', '🔵'),
}


@dataclass
class SesiKuliah:
    kode: str
    mata_kuliah: str
    kelas: str = ''
    sks: str = ''
    dosen: str = ''
    nip: str = ''
    hari_tanggal: str = ''
    tanggal: str = ''
    jam: str = ''
    ruang: str = ''
    pertemuan: int = 0
    warna_class: str = ''
    warna: str = ''          # HIJAU / MERAH / KUNING
    status_absen: str = ''   # teks manusia
    status_icon: str = '⚪'

    @property
    def jam_mulai_menit(self) -> int:
        """Untuk sort: menit sejak 00:00. Unknown → besar."""
        m = re.search(r'(\d{1,2})[.:](\d{2})', self.jam or '')
        if not m:
            return 10**9
        return int(m.group(1)) * 60 + int(m.group(2))

    @property
    def jam_selesai_menit(self) -> int:
        """Akhir sesi dari rentang '08.00 - 10.30'."""
        parts = re.findall(r'(\d{1,2})[.:](\d{2})', self.jam or '')
        if len(parts) >= 2:
            return int(parts[1][0]) * 60 + int(parts[1][1])
        if len(parts) == 1:
            return self.jam_mulai_menit + 120  # fallback 2 jam
        return 10**9


def _now() -> datetime:
    return datetime.now(TZ) if TZ else datetime.now()


def today_str(fmt: str = '%d-%m-%Y') -> str:
    return _now().strftime(fmt)


def today_label() -> str:
    n = _now()
    return f'{HARI_ID[n.weekday()]}, {n.strftime("%d-%m-%Y")}'


def _field(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else ''


def _apply_warna(sesi: SesiKuliah, cls: str) -> None:
    sesi.warna_class = cls or ''
    key = ''
    for k in WARNA_MAP:
        if k in (cls or ''):
            key = k
            break
    if key:
        sesi.warna, sesi.status_absen, sesi.status_icon = WARNA_MAP[key]
    else:
        sesi.warna, sesi.status_absen, sesi.status_icon = '', 'Status tidak diketahui', '⚪'


def parse_jadwal(html: str) -> List[SesiKuliah]:
    m = re.search(r'<tbody>(.*?)</tbody>', html, re.S | re.I)
    if not m:
        return []
    body = m.group(1)
    rows = re.findall(r'<tr>(.*?)</tr>', body, re.S | re.I)
    out: List[SesiKuliah] = []

    for row in rows:
        # td dengan optional class
        tds = re.findall(r'<td(\s[^>]*)?>(.*?)</td>', row, re.S | re.I)
        if len(tds) < 3:
            continue
        kode = re.sub(r'<[^>]+>', '', tds[0][1]).strip()
        mk_html = tds[1][1]
        mk_plain = re.sub(r'<br\s*/?>', '\n', mk_html, flags=re.I)
        mk_plain = re.sub(r'<[^>]+>', '', mk_plain)
        lines = [ln.strip() for ln in mk_plain.splitlines() if ln.strip()]
        mata = lines[0] if lines else ''
        kelas = sks = ''
        for ln in lines[1:]:
            km = re.search(r'Kelas\s*:\s*(.+?)\)?\s*$', ln, re.I)
            if km:
                kelas = km.group(1).strip().rstrip(')')
            sm = re.search(r'SKS[^:]*:\s*(\d+)', ln, re.I)
            if sm:
                sks = sm.group(1)

        for pi, (attrs, cell) in enumerate(tds[2:], start=1):
            cm = re.search(r'class="([^"]*)"', attrs or '')
            cls = cm.group(1) if cm else ''
            text = re.sub(r'<br\s*/?>', '\n', cell, flags=re.I)
            text = re.sub(r'<[^>]+>', '', text)
            text = ' '.join(text.split())
            if 'Hari, tanggal' not in text and 'Jam' not in text:
                continue
            dosen = _field(text, r'Nama\s*:\s*(.+?)(?=\s*NIP\s*:|Hari,|Ruang|Jam|$)')
            nip = _field(text, r'NIP\s*:\s*(\d+)')
            hari_tgl = _field(text, r'Hari,\s*tanggal\s*:\s*(.+?)(?=\s*Ruang\s*:|Jam\s*:|$)')
            ruang = _field(text, r'Ruang\s*:\s*(.+?)(?=\s*Jam\s*:|$)')
            jam = _field(text, r'Jam\s*:\s*([0-9.:\s\-]+)')
            jam = (jam or '').replace('\xa0', '').replace('&nbsp;', '').strip()
            tgl = ''
            tm = re.search(r'(\d{2}-\d{2}-\d{4})', hari_tgl or '')
            if tm:
                tgl = tm.group(1)
            sesi = SesiKuliah(
                kode=kode,
                mata_kuliah=mata,
                kelas=kelas,
                sks=sks,
                dosen=(dosen or '').strip(),
                nip=nip or '',
                hari_tanggal=(hari_tgl or '').strip(),
                tanggal=tgl,
                jam=jam,
                ruang=(ruang or '').strip(),
                pertemuan=pi,
            )
            _apply_warna(sesi, cls)
            out.append(sesi)
    return out


def sesi_hari_ini(semua: List[SesiKuliah], tanggal: Optional[str] = None) -> List[SesiKuliah]:
    tgl = tanggal or today_str()
    hari = [s for s in semua if s.tanggal == tgl]
    hari.sort(key=lambda s: (s.jam_mulai_menit, s.mata_kuliah))
    return hari


def fetch_hari_ini(client) -> List[SesiKuliah]:
    r = client.get('/jadwal_kuliah/index')
    if r.status_code != 200:
        return []
    return sesi_hari_ini(parse_jadwal(r.text))


def ringkas_status(sesi: List[SesiKuliah]) -> dict:
    """Hitung jumlah hijau/merah/kuning."""
    c = {'HIJAU': 0, 'MERAH': 0, 'KUNING': 0, 'LAIN': 0}
    for s in sesi:
        if s.warna in c:
            c[s.warna] += 1
        else:
            c['LAIN'] += 1
    return c


def menit_sekarang() -> int:
    n = _now()
    return n.hour * 60 + n.minute


def dalam_jendela_kuliah(
    sesi: List[SesiKuliah],
    buffer_menit: int = 15,
) -> bool:
    """True jika sekarang di dalam salah satu jam kuliah (± buffer sebelum mulai)."""
    if not sesi:
        return False
    now = menit_sekarang()
    for s in sesi:
        mulai = s.jam_mulai_menit - buffer_menit
        selesai = s.jam_selesai_menit
        if mulai <= now <= selesai:
            return True
    return False
