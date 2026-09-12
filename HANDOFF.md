# HANDOFF — SIMKULIAH Auto-Absensi (record lengkap untuk agent berikutnya)

> **Baca file ini dulu** sebelum mengubah sistem.  
> Dokumen arsitektur modul-per-modul ada di `CLAUDE.md`.  
> File ini = **status produksi + keputusan produk + hasil tes + larangan**, supaya agent sesi berikut tidak mengulang kerja atau merusak flow yang sudah disepakati.

**Terakhir diperbarui:** 2026-09-13 (WIB) — termasuk rapikan struktur folder `scripts/` + `docs/`  
**Repo GitHub:** https://github.com/Athraynmhd/notifikasi-alert  
**Branch:** `main`  
**Commit handoff awal harden:** `0db1293`  
**Author commit:** Athraynmhd `<athar5@mhs.usk.ac.id>` saja (tanpa Co-authored-by Cursor).

---

## 1. Apa sistem ini (satu kalimat)

Otomasi absensi kuliah di **SIMKULIAH USK**: solve CAPTCHA login → cek status absensi + jadwal → kirim Telegram → user tekan tombol **Absen / Tidak** → jika Absen, sistem submit absensi ke SIMKULIAH.

**Target:** `https://simkuliah.usk.ac.id/index.php`

---

## 2. Keputusan produk yang SUDAH DIKUNCI (jangan diubah tanpa minta user)

| Keputusan | Status | Alasan |
|-----------|--------|--------|
| Channel notifikasi | **Telegram saja** | User menolak ntfy/SMS untuk sekarang |
| Mode absen CI | **`confirm` hardcode** di workflow | User **tidak mau full auto**; absen hanya jika tekan tombol di Telegram |
| ntfy (`REF/ntfy`) | **Tidak diintegrasikan** | Hanya referensi; bukan SMS; tidak ganti tombol confirm |
| Multi-user | Belum | Single NIM via secrets |
| Database / web server | Tidak ada | Script + JSON state + cookie file saja |

### Mode absen (kode mendukung 3, produksi pakai 1)

Di `absen_flow.py` / env `ABSEN_MODE`:

| Mode | Perilaku | Dipakai produksi? |
|------|----------|-------------------|
| `confirm` | Kirim inline keyboard → poll ~90s → `do_absen` / skip / timeout | **YA — dikunci di workflow** |
| `auto` | Absen langsung tanpa konfirmasi | Kode ada, **jangan aktifkan** kecuali user minta |
| `notify_only` | Kabari saja, tidak absen | Kode ada, opsional |

**Workflow file:** `.github/workflows/absensi-notify.yml`  
Baris penting: `ABSEN_MODE: confirm` (bukan dari `vars` / input — sengaja dikunci).

---

## 3. Yang dikembangkan di sesi ini (production hardening)

### 3.1 Modul baru

| File | Fungsi |
|------|--------|
| `absen_flow.py` | Orchestration: fingerprint, mode, metrics/alert helpers, `handle_open_absen()`, `run_absen()` |
| `tests/test_production.py` | Unit test parser `state_of` + flow (tanpa network) |
| `tests/fixtures_absensi.py` | HTML fixture OPEN / NOT_OPEN / UNKNOWN |
| `tests/__init__.py` | Package marker |
| `CLAUDE.md` | Dokumentasi arsitektur lengkap (sudah di-commit) |
| **`HANDOFF.md` (file ini)** | Record status + keputusan untuk agent berikutnya |
| `scripts/` | Rapikan: training + measure dipindah dari root |
| `docs/security_research.md` | Dipindah dari root |

### 3.2 Modul yang diubah

| File | Perubahan utama |
|------|-----------------|
| `config.py` | Konstanta production: `ABSEN_MODES`, `ABSEN_MODE_DEFAULT`, `LOGIN_FAIL_ALERT_EVERY`, `PARSER_UNKNOWN_ALERT`, `ABSENSI_MARKERS` |
| `simkuliah.py` | `last_login_stats` (attempts, wrong_captcha, errors, used_cookies, result); diisi di `login()` / `ensure_login()` |
| `ci_notify.py` | Pakai `absen_flow`; metrics di state; alert login gagal beruntun; alert UNKNOWN; mode confirm via `handle_open_absen` |
| `tool.py` | `telegram-test` kirim 3 pesan (OPEN, NOT_OPEN, prompt tombol); perintah baru **`telegram-demo`** (simulasi confirm tanpa SIMKULIAH) |
| `.github/workflows/absensi-notify.yml` | Unit test sebelum notify; `ABSEN_MODE: confirm`; env alert |

### 3.3 Fitur observability

Disimpan di `.ci_state.json` (gitignored, di-cache antar CI run):

```json
{
  "fingerprint": "NOT_OPEN",
  "state": "NOT_OPEN",
  "sesi": 0,
  "in_window": false,
  "login_fail_streak": 0,
  "parser_unknown_streak": 0,
  "last_run_at": "...",
  "last_login_ok": true,
  "absen_mode": "confirm",
  "last_login": {
    "attempts": 2,
    "wrong_captcha": 1,
    "errors": 0,
    "used_cookies": false,
    "result": "LOGIN_OK"
  }
}
```

**Alert Telegram:**
- Login gagal: streak=1 selalu alert, lalu tiap `LOGIN_FAIL_ALERT_EVERY` (default 6) — anti-spam
- `state_of` → `UNKNOWN`: alert (transisi ke UNKNOWN, atau UNKNOWN saat `in_window`)

**Belum ada:** statistik lifetime kumulatif CAPTCHA % (hanya metrik **run terakhir**).

---

## 4. Flow produksi end-to-end (yang harus dipahami agent)

```
GitHub Actions cron (Senin–Sabtu, tiap 5 menit, ~07–19 WIB)
        │
        ▼
  unit tests (tests.test_production)
        │
        ▼
  ci_notify.py
        │
        ├─ ensure_login(cookies)  → CAPTCHA via UltimateSolver jika perlu
        │     └─ gagal → alert (throttle) + save metrics → exit 1
        │
        ├─ report() → state_of(/absensi) + jadwal hari ini
        │
        ├─ fingerprint berubah? + dalam jendela kuliah (±15 menit)?
        │
        ├─ UNKNOWN? → alert parser drift
        │
        └─ jika berubah & allow_notify:
              ├─ OPEN + ada sesi MERAH → handle_open_absen(confirm)
              │     1. send_absen_prompt (tombol Absen / Tidak)
              │     2. poll_callback ≤ 90 detik
              │     3a. do_absen → edit pesan ✅ / ⚠️
              │     3b. skip → edit "⏭️ Absen dilewati."
              │     3c. timeout → edit "⏰ Tidak ada respon (timeout)."
              └─ selain itu → send_message biasa (tanpa tombol)
```

### Personalization jadwal

**BUKAN** hardcode jam kuliah di repo.  
Setelah login dengan NIM user, sistem **fetch jadwal dari SIMKULIAH akun itu** → filter hari ini → buffer `CLASS_BUFFER_MINUTES` (default 15).

### Jadwal cron

- Cron: `*/5 0-11 * * 1-6` (UTC) ≈ Senin–Sabtu 07:00–18:55 WIB  
- **Minggu tidak jalan**  
- Notifikasi aktif terutama di jendela sesi; fingerprint mencegah spam

---

## 5. Balasan Telegram (teks exact yang diedit ke pesan)

Prompt awal (saat OPEN + MERAH):

```
{format_absensi(...)}

❓ Apakah Anda mau absen sekarang?
[+ inline keyboard: ✅ Absen Sekarang | ❌ Tidak]
```

Setelah pilihan (pesan di-**edit**, bukan pesan baru):

| Pilihan | Tambahan di akhir pesan |
|---------|-------------------------|
| Absen berhasil | `✅ Absensi berhasil!\n\n{absen_msg}` |
| Absen gagal | `⚠️ Absensi gagal: {absen_msg}` |
| Tidak | `⏭️ Absen dilewati.` |
| Timeout 90s | `⏰ Tidak ada respon (timeout).` |

`callback_data` harus exact: `do_absen` | `skip_absen` (lihat `telegram_notify.py`).

---

## 6. Hasil tes sungguhan di sesi ini (evidence)

### 6.1 Telegram template + demo confirm (tanpa SIMKULIAH)

- `python tool.py telegram-test` → 3 pesan (OPEN, NOT_OPEN, prompt tombol)  
- `python tool.py telegram-demo --wait 90` → user tekan Absen → pesan diedit sukses demo  
- **Catatan:** `telegram-test` **tidak** poll tombol; `telegram-demo` **ya** poll (tapi tidak hit SIMKULIAH)

### 6.2 E2E sungguhan `ci_notify.py` (login SIMKULIAH + Telegram)

Tanggal tes: **2026-09-13 Minggu ~06:27 WIB**

| Langkah | Hasil |
|---------|--------|
| Cookie lama | Expired |
| CAPTCHA try 1 | `WRONG_CAPTCHA` |
| CAPTCHA try 2 | `LOGIN_OK` |
| State | `NOT_OPEN` |
| Sesi hari itu | `0` (Minggu) |
| Telegram | Terkirim (notifikasi NOT_OPEN, **tanpa tombol** — benar) |
| Siapa yang solve CAPTCHA? | **Kode sistem** (`UltimateSolver`), bukan agent |

Ini membuktikan: login + report + notify jalan. Tombol Absen sungguhan baru muncul hari kuliah saat dosen buka absen.

### 6.3 Unit tests

```bash
python -m unittest tests.test_production -v
```

11 tests, harus OK. Juga dijalankan di CI sebelum `ci_notify.py`.

---

## 7. Cara menjalankan (lokal)

### Env yang dibutuhkan

```
SIMKULIAH_USER
SIMKULIAH_PASS
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Opsional: `ABSEN_MODE`, `ABSEN_WAIT_SECONDS`, `NOTIFY_FORCE=1`, `LOGIN_MAX_TRIES`, `CLASS_BUFFER_MINUTES`

### Perintah berguna

```bash
# Status absensi + jadwal (butuh creds)
python tool.py status --user <NIM> --pass <PASS>

# Tes template Telegram (3 pesan; tombol tidak di-poll)
python tool.py telegram-test

# Demo confirm interaktif (poll tombol; TIDAK absen ke SIMKULIAH)
python tool.py telegram-demo --wait 90

# Flow CI lokal (login sungguhan + notify; force kirim)
set NOTIFY_FORCE=1
set ABSEN_MODE=confirm
python ci_notify.py

# Unit tests
python -m unittest tests.test_production -v
```

Windows PowerShell contoh:

```powershell
$env:SIMKULIAH_USER="..."
$env:SIMKULIAH_PASS="..."
$env:TELEGRAM_BOT_TOKEN="..."
$env:TELEGRAM_CHAT_ID="..."
$env:NOTIFY_FORCE="1"
$env:ABSEN_MODE="confirm"
python ci_notify.py
```

---

## 8. Secrets GitHub (wajib untuk CI)

Repo Variables/Secrets:

| Name | Jenis | Keterangan |
|------|-------|------------|
| `SIMKULIAH_USER` | Secret | NIM |
| `SIMKULIAH_PASS` | Secret | Password |
| `TELEGRAM_BOT_TOKEN` | Secret | Bot token |
| `TELEGRAM_CHAT_ID` | Secret | Chat ID tujuan |

**KEAMANAN (penting untuk agent & user):**  
Di sesi 2026-09-13, kredensial Telegram token + password SIMKULIAH sempat tertulis di chat.  
**Jangan tulis ulang secret ke file/commit.** Sarankan user: rotate BotFather token + ganti password SIMKULIAH + update GitHub Secrets.

File **jangan di-commit** (sudah di `.gitignore`):

- `.ci_cookies.json`
- `.ci_state.json`
- `.env*`

---

## 9. Aturan teknis kritis (jangan dilanggar)

1. **CAPTCHA consume-on-wrong** — satu tebakan per attempt; session/CAPTCHA baru tiap retry. Jangan multi-submit satu gambar.  
2. **`state_of()` di `tool.py`** = ground truth klasifikasi OPEN / NOT_OPEN / UNKNOWN.  
3. **`do_absen()` heuristik HTML** — jika UI SIMKULIAH berubah, update regex + tambah fixture test.  
4. **`glyph_dict.json` ~3MB** — pakai singleton `char_solver.get_solver()`, jangan load berulang.  
5. **Timezone** = `Asia/Jakarta` (WIB). Cron GitHub = UTC.  
6. **Commit GitHub:** user minta **tanpa** `Co-authored-by: Cursor`. Cursor sering menyisipkan trailer otomatis — strip dengan `git commit-tree` / skrip jika perlu sebelum push.  
7. **Jangan aktifkan `ABSEN_MODE=auto` di workflow** tanpa izin eksplisit user.  
8. **Jangan integrasi ntfy/SMS** tanpa diminta.  
9. **Jangan commit secret / cookie / state.**

---

## 10. Peta file aktif vs referensi

### Aktif (produksi — root)

```
config.py, captcha_utils.py, solver_ocr.py, captcha_solver.py, soft_char.py,
char_solver.py, font_solver.py, datadir.py,
simkuliah.py, jadwal.py, tool.py,
telegram_notify.py, absen_flow.py, ci_notify.py,
.github/workflows/absensi-notify.yml,
tests/, data/glyph_dict.json (+ soft_char.npz dll.),
CLAUDE.md, HANDOFF.md, README.md
```

### Scripts (manual, bukan cron)

```
scripts/training/   → collect_more, cluster_glyphs, build_dict, harvest_labels, synth_dict
scripts/measure/    → oracle_test, measure_multi, measure_bypass, test_opt
```

### Referensi / tidak dipakai produksi

- `archive/` — probe lama  
- `docs/security_research.md` — catatan riset  
- `REF/ntfy/` — jika ada di mesin lokal: **bukan** dependency; jangan diintegrasikan tanpa minta user

---

## 11. Checklist “sistem cukup untuk dipakai sehari-hari”

- [x] Login + CAPTCHA otomatis  
- [x] Jadwal personal dari akun SIMKULIAH  
- [x] Telegram notify  
- [x] Confirm Absen/Tidak (bukan auto)  
- [x] Cron weekday jam kuliah  
- [x] Cookie reuse antar CI  
- [x] Alert login gagal / UNKNOWN  
- [x] Unit test parser  
- [x] E2E lokal terbukti (login + NOT_OPEN notify)  
- [ ] E2E tombol Absen **saat OPEN sungguhan** (belum, karena tes di hari Minggu / absen belum dibuka)  
- [ ] Rotate secrets yang sempat bocor di chat  
- [ ] Lifetime CAPTCHA success-rate (opsional, belum dibuat)

---

## 12. Jika agent berikutnya diminta lanjut — prioritas aman

1. **Jangan rewrite arsitektur.** Fondasi sudah production-ready untuk Telegram confirm.  
2. Kalau user mau uji Absen sungguhan → jalankan `ci_notify` / force di **hari & jam kuliah** saat status OPEN.  
3. Kalau parser rusak → dump HTML `/absensi`, update `state_of` + fixture di `tests/`.  
4. Kalau CAPTCHA jelek → ukur dengan `measure_bypass.py` / harvest; jangan ganti ke DL tanpa bukti.  
5. Kalau diminta ntfy → jelaskan ulang: bagus untuk notify-only, **bukan** pengganti tombol confirm; tunggu keputusan user.  
6. Baca `CLAUDE.md` untuk detail tiap modul; file ini untuk **keputusan & status**.

---

## 13. Perintah cepat verifikasi kesehatan

```bash
python -m unittest tests.test_production -v
python -c "from absen_flow import get_absen_mode; assert get_absen_mode('confirm')=='confirm'"
```

Cek workflow masih terkunci confirm:

```bash
# harus mengandung: ABSEN_MODE: confirm
rg "ABSEN_MODE" .github/workflows/absensi-notify.yml
```

---

*Akhir HANDOFF. Pertahankan file ini tetap akurat setiap kali ada keputusan produk atau perubahan flow produksi.*
