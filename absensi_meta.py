"""Parser meta absensi: Batas Absen, sudah absen, eligibility tombol Absen.

Batas Absen = teks HTML (bukan OCR/vision). Contoh nilai sel:
- \"09:05\" / \"09.05\" → deadline jam
- \"Dosen belum absen\" → belum bisa absen
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

from jadwal import menit_sekarang


@dataclass
class SesiAbsensiPage:
    judul: str
    jam: str
    ruang: str
    batas_text: str
    batas_menit: Optional[int]  # menit sejak 00:00 jika jam; else None
    dosen_belum_absen: bool
    sudah_absen: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TIME_RE = re.compile(r'^(\d{1,2})[:.](\d{2})$')


def parse_jam_ke_menit(text: str) -> Optional[int]:
    """Parse '09:05' / '09.05' → menit sejak 00:00."""
    t = (text or '').strip()
    m = _TIME_RE.match(t)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def _cell_text(html: str) -> str:
    t = re.sub(r'<[^>]+>', ' ', html)
    return ' '.join(t.split()).strip()


def parse_sesi_absensi(html: str) -> list[SesiAbsensiPage]:
    """Ambil semua blok tabel yang punya kolom Batas Absen."""
    out: list[SesiAbsensiPage] = []
    for m in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.I | re.S):
        body = m.group(1)
        if not re.search(r'Batas\s*Absen', body, re.I):
            continue
        headers = [_cell_text(h) for h in re.findall(r'<th[^>]*>(.*?)</th>', body, re.I | re.S)]
        if not any(re.search(r'Batas\s*Absen', h, re.I) for h in headers):
            continue
        try:
            i_batas = next(i for i, h in enumerate(headers) if re.search(r'Batas\s*Absen', h, re.I))
        except StopIteration:
            continue
        i_jam = next((i for i, h in enumerate(headers) if h.lower() == 'jam'), None)
        i_ruang = next((i for i, h in enumerate(headers) if h.lower() == 'ruang'), None)

        ctx_start = max(0, m.start() - 3500)
        ctx = html[ctx_start:m.end()]
        ctx_lower = ctx.lower()
        # Prioritas teks status di blok yang sama
        if re.search(r'Anda\s+sudah\s+absen', ctx, re.I):
            sudah = True
        elif re.search(r'Anda\s+belum\s+absen', ctx, re.I):
            sudah = False
        else:
            sudah = False

        judul_m = re.search(
            r'Absensi\s+Kelas[^|<]{0,180}',
            re.sub(r'<[^>]+>', ' ', ctx),
            re.I,
        )
        judul = ' '.join(judul_m.group(0).split()) if judul_m else ''

        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', body, re.I | re.S):
            cells = [_cell_text(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.I | re.S)]
            if len(cells) <= i_batas:
                continue
            batas_text = cells[i_batas]
            dosen_belum = bool(re.search(r'Dosen\s+belum\s+absen', batas_text, re.I))
            batas_menit = None if dosen_belum else parse_jam_ke_menit(batas_text)
            jam = cells[i_jam] if i_jam is not None and i_jam < len(cells) else ''
            ruang = cells[i_ruang] if i_ruang is not None and i_ruang < len(cells) else ''
            out.append(SesiAbsensiPage(
                judul=judul,
                jam=jam,
                ruang=ruang,
                batas_text=batas_text,
                batas_menit=batas_menit,
                dosen_belum_absen=dosen_belum,
                sudah_absen=sudah,
            ))
    return out


def state_from_batas(sesi: list[SesiAbsensiPage]) -> tuple[str, str]:
    """Ground truth OPEN/NOT_OPEN dari kolom Batas Absen (bukan tombol).

    Flow SIMKULIAH:
    - \"Dosen belum absen\" → belum dibuka (perlu refresh/poll)
    - terisi jam (mis. 09:05) → dosen sudah absen, jendela 15 menit sampai jam itu
    """
    if not sesi:
        return 'UNKNOWN', 'Tidak ada tabel Batas Absen'
    # Ada deadline jam → dosen sudah membuka (minimal satu sesi)
    opened = [s for s in sesi if s.batas_menit is not None]
    if opened:
        aktif = [s for s in opened if not s.sudah_absen]
        if aktif:
            return 'OPEN', f'Dosen sudah absen — Batas Absen {aktif[0].batas_text}'
        return 'NOT_OPEN', 'Batas Absen ada tapi Anda sudah absen / tidak ada sesi aktif'
    if any(s.dosen_belum_absen for s in sesi):
        return 'NOT_OPEN', 'Dosen belum absen (kolom Batas Absen)'
    return 'UNKNOWN', 'Batas Absen tidak dikenali'


def pilih_sesi_bisa_absen(
    sesi: list[SesiAbsensiPage],
    *,
    now_menit: Optional[int] = None,
) -> tuple[Optional[SesiAbsensiPage], str]:
    """Pilih sesi yang masih boleh diabsen.

    Return (sesi|None, reason):
      within_batas | sudah_absen | dosen_belum | expired | none
    """
    now = menit_sekarang() if now_menit is None else now_menit
    expired: list[SesiAbsensiPage] = []
    for s in sesi:
        if s.sudah_absen:
            continue
        if s.dosen_belum_absen or s.batas_menit is None:
            continue
        if now <= s.batas_menit:
            return s, 'within_batas'
        expired.append(s)
    if any(s.sudah_absen for s in sesi) and not expired:
        # ada yang sudah absen, tidak ada yang masih open
        if all(s.sudah_absen or s.dosen_belum_absen for s in sesi):
            return None, 'sudah_absen_or_belum'
    if expired:
        return expired[0], 'expired'
    if any(s.dosen_belum_absen for s in sesi):
        return None, 'dosen_belum'
    if any(s.sudah_absen for s in sesi):
        return None, 'sudah_absen'
    return None, 'none'


def boleh_kirim_tombol_absen(
    *,
    state: str,
    sesi_page: list[SesiAbsensiPage],
    ada_merah_jadwal: bool,
    now_menit: Optional[int] = None,
) -> tuple[bool, str, Optional[SesiAbsensiPage]]:
    """Tombol Absen hanya jika Batas Absen = jam DAN sekarang masih <= batas.

    Tidak mengandalkan tombol HTML (bisa ada meski dosen belum absen).
    """
    del state, ada_merah_jadwal  # state UI lama; ground truth = Batas Absen
    target, reason = pilih_sesi_bisa_absen(sesi_page, now_menit=now_menit)
    if reason == 'within_batas' and target is not None:
        return True, reason, target
    return False, reason, target


def format_batas_line(sesi: Optional[SesiAbsensiPage], reason: str) -> str:
    if reason == 'within_batas' and sesi:
        return f'⏱️ Batas absen: {sesi.batas_text} (jam {sesi.jam or "—"})'
    if reason == 'expired' and sesi:
        return f'⏰ Batas absen {sesi.batas_text} sudah lewat (jam {sesi.jam or "—"}) — tidak bisa absen.'
    if reason == 'dosen_belum':
        return '⏳ Dosen belum absen — menunggu dibuka.'
    if reason in ('sudah_absen', 'sudah_absen_or_belum'):
        return '✅ Anda sudah absen (atau menunggu sesi berikutnya).'
    return ''
