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

## GitHub Actions

Cron **dimatikan** (GitHub runner tidak bisa reach SIMKULIAH USK).  
Manual: **Actions → Absensi Notify → Run workflow** (opsional).

**Produksi harian:** Windows Task Scheduler `SIMKULIAH-Absensi-Notify`  
- Script: `scripts/local_notify.ps1`  
- Secrets: file `.env` di root (lihat `.env.example`)  
- Pasang ulang: `powershell -File scripts/install_local_task.ps1`

### Secrets GitHub (opsional, untuk manual workflow)

| Name | Isi |
|---|---|
| `SIMKULIAH_USER` | NIM |
| `SIMKULIAH_PASS` | Password |
| `TELEGRAM_BOT_TOKEN` | Token bot dari BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram |

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
