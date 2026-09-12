# Notifikasi Absensi SIMKULIAH

Cek status absensi SIMKULIAH USK dan kirim alert ke Telegram (termasuk jadwal hari ini + warna absen hijau/merah).

Absen hanya setelah Anda tekan tombol **Absen Sekarang** di Telegram (mode `confirm`).

## Struktur folder (ringkas)

| Path | Isi |
|------|-----|
| Root `*.py` | Runtime produksi + entry (`ci_notify.py`, `tool.py`) |
| `scripts/training/` | Panen/latih template CAPTCHA |
| `scripts/measure/` | Ukur akurasi solver |
| `tests/` | Unit test parser & flow |
| `data/` | `glyph_dict.json` + model |
| `docs/` | Catatan riset tambahan |
| `HANDOFF.md` / `CLAUDE.md` | Panduan agent & arsitektur |

## GitHub Actions (jalan otomatis tanpa laptop)

Workflow: `.github/workflows/absensi-notify.yml`  
Jadwal: tiap **5 menit**, Senin–Sabtu, ±07:00–18:55 WIB.  
Notifikasi aktif terutama **di jendela jam kuliah** (±15 menit sebelum mulai sampai selesai).  
Setiap run mencoba **reuse cookie session**; login+CAPTCHA hanya jika cookie expired.  
Telegram **hanya jika status berubah** (mis. dosen buka absen / warna jadwal berubah). Setelah status stabil, **tidak spam**.

### Secrets (Settings → Secrets and variables → Actions)

| Name | Isi |
|---|---|
| `SIMKULIAH_USER` | NIM |
| `SIMKULIAH_PASS` | Password |
| `TELEGRAM_BOT_TOKEN` | Token bot dari BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram |

Setelah secrets diisi: **Actions → Absensi Notify → Run workflow** (centang force untuk tes pertama).

## Lokal

```bash
pip install -r requirements.txt
# butuh Tesseract OCR

set TELEGRAM_BOT_TOKEN=...
set TELEGRAM_CHAT_ID=...
python tool.py status --user NIM --pass PASS --notify
python tool.py monitor --user NIM --pass PASS --interval 60
python tool.py telegram-demo --wait 90
python -m unittest tests.test_production -v
```

## Catatan

- Hanya kirim Telegram jika status berubah (state disimpan di cache CI).
- Endpoint `jadwal_kuliah_hari_ini` di server sering HTTP 500; jadwal diambil dari `/jadwal_kuliah/index`.
- Detail lengkap untuk developer/agent: lihat `HANDOFF.md` dan `CLAUDE.md`.
