# Notifikasi Absensi SIMKULIAH

Cek status absensi SIMKULIAH USK dan kirim alert ke Telegram (termasuk jadwal hari ini + warna absen hijau/merah).

## GitHub Actions (jalan otomatis tanpa laptop)

Workflow: `.github/workflows/absensi-notify.yml`  
Jadwal: tiap **10 menit**, Senin–Sabtu, ±07:00–18:50 WIB.

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
```

## Catatan

- Hanya kirim Telegram jika status berubah (state disimpan di cache CI).
- Endpoint `jadwal_kuliah_hari_ini` di server sering HTTP 500; jadwal diambil dari `/jadwal_kuliah/index`.
