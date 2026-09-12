# SIMKULIAH Auto-Absensi System

## Apa Ini?

Sistem otomatis untuk absensi kuliah di **SIMKULIAH USK** (Universitas Syiah Kuala).
Website SIMKULIAH dilindungi CAPTCHA 5 karakter alfanumerik pada halaman login.
Sistem ini memecahkan CAPTCHA tersebut secara otomatis, login, mengecek status absensi,
dan mengirim notifikasi ke Telegram — termasuk fitur absen langsung dari Telegram.

**Target URL:** `https://simkuliah.usk.ac.id/index.php`

---

## Arsitektur: Peta File Lengkap

```
D:\learn\absen\
│
├── config.py                 # Konstanta terpusat (URL, threshold, path)
│
│   ── CAPTCHA SOLVING PIPELINE ──
├── captcha_utils.py          # Session HTTP, fetch CAPTCHA, segmentasi glyph
├── solver_ocr.py             # Solver via Tesseract OCR (multi-resep voting)
├── font_solver.py            # Solver via font rendering + IoU matching
├── captcha_solver.py         # GlyphSolver: template matching dari glyph_dict.json
├── soft_char.py              # SoftmaxChar: mini logistic regression classifier
├── char_solver.py            # UltimateSolver: ensemble semua solver di atas
│
│   ── HTTP CLIENT ──
├── simkuliah.py              # SIMKULIAH class: login, session, cookie, do_absen
│
│   ── JADWAL & STATUS ──
├── jadwal.py                 # Parser jadwal kuliah + warna status absensi
├── tool.py                   # CLI entrypoint: login/status/monitor/telegram-test
│
│   ── TELEGRAM ──
├── telegram_notify.py        # Kirim notifikasi + inline keyboard + poll callback
├── absen_flow.py             # Orchestration production: mode, metrics, alert, absen
├── ci_notify.py              # CI entrypoint: cron job GitHub Actions
│
│   ── DATA COLLECTION (untuk melatih solver) ──
├── collect_more.py           # Kumpulkan glyph mentah dari CAPTCHA
├── cluster_glyphs.py         # Klaster glyph serupa via IoU
├── build_dict.py             # Bangun glyph_dict.json dari klaster berlabel
├── harvest_labels.py         # Auto-harvest label benar via dummy login
├── synth_dict.py             # Tambah template sintetis dari system font
├── datadir.py                # Alias path backward-compat → config.py
│
│   ── TESTING & MEASUREMENT ──
├── oracle_test.py            # Online test akurasi GlyphSolver (dummy creds)
├── measure_multi.py          # Ukur multi-strategi (OCR voting)
├── measure_bypass.py         # Ukur bypass rate UltimateSolver
├── test_opt.py               # Test lokal self-match + opsional online
├── tests/                    # Unit tests production (parser + flow, no network)
│   ├── test_production.py
│   └── fixtures_absensi.py   # HTML fixtures state_of()
│
│   ── CI/CD ──
├── .github/workflows/
│   └── absensi-notify.yml    # Cron tiap 5 menit, Senin-Sabtu, 07-19 WIB
│
│   ── DATA ──
├── data/
│   ├── glyph_dict.json       # ~3MB, 17 karakter, 80 template/karakter
│   ├── glyph_meta.json       # Metadata glyph yang dikumpulkan
│   ├── cluster_assign.json   # Mapping file → cluster ID
│   ├── best_fonts.json       # Top 5 font yang cocok (tahoma, lucon, dll)
│   ├── soft_char.npz         # Model softmax terlatih
│   ├── font_cache.npz        # Cache rendered font templates
│   ├── glyphs/               # (gitignored) PNG glyph mentah
│   └── tmp/                  # (gitignored) temp file OCR
│
│   ── LAINNYA ──
├── archive/                  # Script eksplorasi/probe lama (tidak dipakai)
├── requirements.txt          # requests, Pillow, numpy
├── .gitignore
└── .ci_cookies.json          # Cookie session CI (gitignored runtime)
```

---

## Detail Setiap Modul

### `config.py` — Pusat Konfigurasi

Semua konstanta ada di sini. Modul lain `from config import ...`.

| Konstanta | Nilai | Fungsi |
|-----------|-------|--------|
| `BASE_URL` | `https://simkuliah.usk.ac.id/index.php` | Root URL SIMKULIAH |
| `CAPTCHA_CHAR_COUNT` | `5` | CAPTCHA selalu 5 karakter |
| `SOLVER_MIN_CONF` | `0.60` | Threshold confidence minimum |
| `LOGIN_MAX_TRIES` | `15` | Max percobaan login (tiap percobaan = CAPTCHA baru) |
| `LOGIN_RETRY_DELAY` | `0.3` detik, exponential backoff 1.5x | Delay antar retry |
| `CELL_H, CELL_W` | `36, 24` | Ukuran cell normalisasi glyph |
| `TELEGRAM_BOT_TOKEN` | dari env | Token bot Telegram |
| `TELEGRAM_CHAT_ID` | dari env | Chat ID tujuan notifikasi |
| `ABSEN_MODES` | confirm / auto / notify_only | Mode absen production |
| `ABSEN_MODE_DEFAULT` | `confirm` | Default jika env kosong/invalid |
| `LOGIN_FAIL_ALERT_EVERY` | `6` | Alert login gagal tiap N streak (plus streak=1) |
| `PARSER_UNKNOWN_ALERT` | `1` | Alert jika state_of → UNKNOWN |

### `absen_flow.py` — Orchestration Production

Shared logic untuk CI (dan bisa dipakai lokal):

- `get_absen_mode()` → `confirm` | `auto` | `notify_only`
- `fingerprint(info)` → hash state+jadwal untuk anti-spam
- `handle_open_absen(...)` → jalur OPEN+MERAH sesuai mode
- `merge_metrics()` / `should_alert_login_fail()` / `should_alert_parser_unknown()`
- `run_absen()` → re-login jika session expired, lalu `do_absen()`

**Mode absen (`ABSEN_MODE`):**
| Mode | Perilaku |
|------|----------|
| `confirm` | Kirim tombol Telegram, tunggu `ABSEN_WAIT_SECONDS` (default 90s) |
| `auto` | Absen langsung, kirim hasil ke Telegram (tanpa wait) |
| `notify_only` | Kabari saja; tidak submit absen |

### `captcha_utils.py` — Utilitas CAPTCHA

- `new_session()` → `requests.Session` dengan User-Agent
- `fetch_captcha(session)` → bytes PNG CAPTCHA (fetch halaman login dulu untuk cookie, lalu ambil gambar)
- `read_rgb(png_bytes)` → numpy array RGB int16
- `strength(array)` → (strong_mask, soft_mask) binary berdasarkan saturasi+luminance
- `find_char_columns(array)` → list of (x_position, glyph_mask) — segmentasi 5 karakter via run-length pada kolom ink

**PENTING:** Server meregenerasi CAPTCHA setelah jawaban salah. Jadi setiap attempt = session baru + CAPTCHA baru. Tidak bisa retry dengan CAPTCHA yang sama.

### `solver_ocr.py` — Tesseract OCR Solver

- 8 resep berbeda (kombinasi scale 3-6x, psm 7/8, whitelist digit/alnum)
- Setiap resep menghasilkan vote jika hasilnya tepat 5 karakter
- `best_guess(img)` → majority vote, preferensi digit, confusable mapping (O→0, S→5, dll)
- Fallback: OCR per-glyph (segmentasi dulu, OCR tiap karakter)

### `font_solver.py` — Font Template Solver

- Render karakter dari system font (16 kandidat font)
- `to_cell(mask)` → normalisasi glyph ke cell 36x24 (center, scale preserving aspect ratio)
- `iou(a, b)` / `iou_batch(query, templates)` → Intersection-over-Union matching
- `FontSolver` class: cache template ke .npz, recognize via batch IoU
- **Hanya dipakai oleh synth_dict.py untuk generate template sintetis**

### `captcha_solver.py` — GlyphSolver (Template Matching)

- Load glyph_dict.json (17 chars × ~80 templates = ~1360 templates)
- Mega-stack: semua template di-flatten ke satu matrix (N, H*W)
- `recognize(glyph)` → top-k (char, score) via satu matmul
- `solve(img)` → full 5-char guess dengan confidence per karakter
- `solve_strict(img, min_conf)` → hanya return jika SEMUA karakter ≥ min_conf

### `soft_char.py` — SoftmaxChar (Logistic Regression)

- Multinomial logistic regression di atas flattened cell
- Train dari glyph_dict.json (default: digit only)
- `predict(glyph, topk)` → list of (char, probability)
- Model disimpan di `data/soft_char.npz`

### `char_solver.py` — UltimateSolver (Ensemble)

**Ini solver utama yang dipakai saat login.**

```
UltimateSolver.best_guess(img):
  1. CharEnsemble.solve(img):
     a. Segmentasi 5 glyph
     b. Per glyph:
        - GlyphSolver.recognize() → top-3, weight 3.0/2.3/1.6
        - SoftmaxChar.predict()   → top-3, weight 2.5/1.9/1.3
        - Confusable mapping (O→0, S→5, dll) dengan weight 85%
        - Best = max weighted vote
     c. Return full 5-char guess + per-char confidence

  2. Jika confidence rendah (worst < 0.60):
     - Fallback ke solver_ocr.best_guess() (Tesseract)
     - Tambah vote dengan weight 2.0

  3. Final scoring: vote count → digit preference → penalti huruf
  4. Reject jika < 3 digit (lebih baik gagal → dapat CAPTCHA baru)
```

**Singleton:** `get_solver()` returns cached `UltimateSolver` instance.

### `simkuliah.py` — HTTP Client

```python
class SIMKULIAH:
    # Login flow:
    _new()           → session baru + fetch CAPTCHA → RGB array
    best_captcha()   → UltimateSolver.best_guess() || solver_ocr fallback
    _post_login()    → POST /login/auth {username, password, captcha_answer}
                       Return: LOGIN_OK | BAD_CREDS | WRONG_CAPTCHA | ERROR
    login_attempt()  → _new() + best_captcha() + _post_login() (1 attempt)
    login()          → retry login_attempt() up to max_tries; isi last_login_stats
    logged_in()      → cek session masih valid (GET /absensi, cek redirect)
    ensure_login()   → load cookie → cek valid → login jika perlu → save cookie
                       last_login_stats.result = COOKIE_OK | LOGIN_OK | ...

    # Cookie persistence:
    save_cookies()   → JSON {cookies: {...}, saved_at: timestamp}
    load_cookies()   → muat dari file, inject ke session

    # Absensi:
    do_absen()       → GET /absensi → cari form/link do_absen → submit → verify
                       1. Cari <form action="...do_absen..."> → POST dengan hidden fields
                       2. Fallback: <a href="...do_absen..."> → GET
                       3. Fallback: btn-absen class → extract href
                       4. _verify_absen(): re-fetch /absensi, cek status berubah
                       Return: (bool success, str message)

    # Generic:
    get(path)        → session.get(BASE_URL + path)
```

### `jadwal.py` — Parser Jadwal

```python
@dataclass SesiKuliah:
    kode, mata_kuliah, kelas, sks, dosen, nip
    hari_tanggal, tanggal, jam, ruang, pertemuan
    warna_class  → CSS class dari tabel (table-success, table-danger, dll)
    warna        → HIJAU | MERAH | KUNING (abstraksi warna)
    status_absen → teks manusia ("Sudah absen", "Belum absen", dll)
    status_icon  → emoji (🟢, 🔴, 🟡)
    jam_mulai_menit  → property: menit sejak 00:00 (untuk sort)
    jam_selesai_menit → property: akhir sesi

parse_jadwal(html)      → List[SesiKuliah] dari tabel HTML /jadwal_kuliah
sesi_hari_ini(semua)    → filter hari ini, sort by jam
fetch_hari_ini(client)  → GET /jadwal_kuliah/index → parse → filter hari ini
dalam_jendela_kuliah()  → True jika sekarang dalam rentang jam kuliah (±buffer)
ringkas_status()        → {HIJAU: n, MERAH: n, KUNING: n}
```

**Warna mapping:**
- `table-success` → HIJAU → Sudah absen 🟢
- `table-danger` → MERAH → Belum absen 🔴
- `table-warning` → KUNING → Belum dilaksanakan 🟡

### `tool.py` — CLI Tool

```
python tool.py <command> --user <NIM> --pass <password>

Commands:
  login          → test login saja
  status         → login + tampilkan status absensi + jadwal (--json, --notify)
  monitor        → loop infinite: cek status tiap --interval detik, kirim Telegram jika berubah
  telegram-test  → kirim 2 contoh pesan Telegram (OPEN + NOT_OPEN)

Fungsi penting:
  state_of(html) → ('OPEN'|'NOT_OPEN'|'UNKNOWN', detail_string)
    - "belum masuk waktu absen" → NOT_OPEN
    - "btn-absen" atau "do_absen" (tanpa "belum masuk waktu") → OPEN
    - "masuk" + "absen" (tanpa "belum") → OPEN
    - lainnya → UNKNOWN

  extract_mahasiswa(html) → nama mahasiswa dari profil page
  report(client) → dict {absensi: {state, detail, http, mahasiswa}, jadwal_hari_ini: [...], _sesi_obj: [...]}
```

### `telegram_notify.py` — Notifikasi Telegram

**API:** `https://api.telegram.org/bot{token}/{method}`

**Fungsi kirim pesan:**
- `send_message(text)` → plain text, return bool
- `send_absen_prompt(text)` → pesan dengan inline keyboard [✅ Absen Sekarang] [❌ Tidak], return message_id
- `edit_message(message_id, text)` → update pesan (hapus tombol)
- `_truncate(text)` → potong jika > 4096 char (limit Telegram)

**Fungsi interaktif:**
- `poll_callback(wait_seconds=90)`:
  1. Flush stale updates (getUpdates offset=-1)
  2. Long-poll getUpdates (timeout 30s per batch, total 90s)
  3. Filter callback_query by chat_id
  4. answerCallbackQuery (hilangkan loading spinner)
  5. Return 'do_absen' | 'skip_absen' | None (timeout)

**Format pesan:**
- `format_absensi(state, detail, sesi, mahasiswa)` → pesan lengkap:
  - Header: 🟢 ABSENSI SUDAH DIBUKA / 🔴 BELUM DIBUKA / ⚪ TIDAK JELAS
  - Tanggal + jam cek
  - Nama mahasiswa
  - Ringkasan jadwal (n mata kuliah, n sudah/belum/menunggu)
  - Detail per sesi (kode, nama MK, jam, ruang, dosen, status)
  - Link SIMKULIAH

### `ci_notify.py` — CI Entry Point (GitHub Actions)

**Environment variables (dari GitHub Secrets / Vars):**
```
SIMKULIAH_USER        → NIM
SIMKULIAH_PASS        → password
TELEGRAM_BOT_TOKEN    → token bot
TELEGRAM_CHAT_ID      → chat ID tujuan
NOTIFY_FORCE          → "1" untuk paksa kirim
ABSEN_MODE            → confirm | auto | notify_only (default confirm)
ABSEN_WAIT_SECONDS    → detik tunggu respon Telegram (default 90, hanya mode confirm)
LOGIN_FAIL_ALERT_EVERY → alert login gagal tiap N streak (default 6; streak=1 selalu alert)
PARSER_UNKNOWN_ALERT  → "1" alert jika state_of → UNKNOWN
ABSEN_STATE_PATH      → path file state (default .ci_state.json)
ABSEN_COOKIES_PATH    → path file cookie (default .ci_cookies.json)
CLASS_BUFFER_MINUTES  → buffer menit sebelum jam kuliah (default 15)
LOGIN_MAX_TRIES       → max percobaan login (default 15)
TESSERACT_PATH        → /usr/bin/tesseract (CI)
```

**Flow utama `main()`:**
```
1. Validasi env vars
2. ensure_login (cookie reuse → login jika perlu) + catat last_login_stats
3. Jika login gagal:
   → update login_fail_streak; alert Telegram (throttle); exit 1
4. report() → state + jadwal
5. fingerprint() → hash state+jadwal
6. Bandingkan fingerprint dengan .ci_state.json sebelumnya
7. Cek dalam jendela jam kuliah?
8. Jika state UNKNOWN → alert parser drift (throttle)
9. Jika berubah DAN dalam jendela:
   a. Jika OPEN + ada MERAH (belum absen):
      → absen_flow.handle_open_absen() sesuai ABSEN_MODE
         confirm: prompt + poll 90s
         auto: do_absen langsung + kirim hasil
         notify_only: kabari saja
   b. Selain itu → send_message() biasa
10. save_state() → fingerprint + metrics (streak, last_login, mode)
```

**State file (.ci_state.json):**
```json
{
  "fingerprint": "OPEN||FPPS1001|MERAH|16.35 - 18.15|Belum absen",
  "state": "OPEN",
  "sesi": 1,
  "in_window": true,
  "login_fail_streak": 0,
  "parser_unknown_streak": 0,
  "last_login_ok": true,
  "absen_mode": "confirm",
  "last_login": {
    "attempts": 0,
    "wrong_captcha": 0,
    "errors": 0,
    "used_cookies": true,
    "result": "COOKIE_OK"
  }
}
```

### `.github/workflows/absensi-notify.yml` — CI Workflow

- **Schedule:** `*/5 0-11 * * 1-6` → tiap 5 menit, jam 00-11 UTC (07-18 WIB), Senin-Sabtu
- **Concurrency:** `absensi-notify`, cancel-in-progress: false (antri, tidak cancel)
- **Timeout:** 15 menit
- **Unit tests:** `python -m unittest tests.test_production -v` sebelum notify
- **Cache:** `.ci_state.json` + `.ci_cookies.json` persist antar run
- **System deps:** tesseract-ocr, fonts-dejavu-core
- **Python deps:** dari requirements.txt (requests, Pillow, numpy)
- **ABSEN_MODE:** dari workflow_dispatch input, atau repo Variable `ABSEN_MODE`, default `confirm`

---

## CAPTCHA Solving Pipeline — Detail

### Karakter yang dikenali
Digits: `0123456789` (80 template masing-masing)
Huruf: `G J Q S Z g j` (1-80 template, huruf kecil g/j jarang)

### Data training
1. **Harvest otomatis** (`harvest_labels.py`): submit CAPTCHA dengan dummy creds → jika server bilang "Username salah" (bukan "CAPTCHA salah"), berarti CAPTCHA benar → simpan glyph + label
2. **Sintetis** (`synth_dict.py`): render karakter dari system font terbaik (tahoma, lucon, calibri, seguisb, trebucbd) dengan variasi skala + dilate/erode
3. **Manual labeling** (`build_dict.py`): cluster → label manual per cluster ID

### Template matching
- Semua template dinormalisasi ke cell 36×24 pixel binary
- IoU (Intersection over Union) sebagai similarity metric
- Mega-stack: semua template di-flatten → satu matmul untuk scoring semua sekaligus

---

## Worst Cases yang Sudah Ditangani

1. **Stale Telegram callback** — `poll_callback()` flush old updates sebelum mulai polling
2. **Session expired selama 90s wait** — `ci_notify.py` cek `logged_in()` dan re-login sebelum `do_absen()`
3. **Hidden input scope** — regex ambil input hanya dari dalam `<form>` yang mengandung `do_absen`
4. **HTTP 200 ≠ absen berhasil** — `_verify_absen()` re-fetch /absensi dan cek status berubah
5. **Pesan Telegram > 4096 char** — `_truncate()` potong pesan
6. **CAPTCHA server regenerasi** — setiap attempt = session baru, satu tebakan saja
7. **Cookie expired** — `ensure_login()` cek dulu, login ulang jika perlu
8. **CI run overlap** — concurrency group di workflow (antri, tidak parallel)
9. **CAPTCHA unreadable** — reject jika < 3 digit, lebih baik gagal → CAPTCHA baru
10. **Network timeout** — semua request punya timeout 25 detik, di-catch

---

## Cara Menjalankan

### Lokal (Windows)
```bash
# Status check
python tool.py status --user <NIM> --pass <password>

# Monitor (loop)
python tool.py monitor --user <NIM> --pass <password> --interval 60

# Test Telegram
export TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy
python tool.py telegram-test

# Test CAPTCHA solver
python test_opt.py              # lokal
python test_opt.py --online 8   # online dengan dummy creds
```

### CI (GitHub Actions)
Otomatis via cron. Manual trigger: workflow_dispatch dengan `force=true` dan/atau `absen_mode`.

Secrets yang dibutuhkan di GitHub:
- `SIMKULIAH_USER`
- `SIMKULIAH_PASS`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional repo Variable:
- `ABSEN_MODE` = `confirm` | `auto` | `notify_only`

Unit test lokal:
```bash
python -m unittest tests.test_production -v
```

---

## Konvensi Kode

- Python 3.11+, `from __future__ import annotations`
- Logging via `logging.getLogger(__name__)`
- Semua path via `config.py` (never hardcode)
- Timezone: `Asia/Jakarta` via `zoneinfo`
- HTTP: `requests` library, semua ada timeout
- Dependencies: hanya `requests`, `Pillow`, `numpy` (plus `tesseract-ocr` system package)
- Tidak ada database, tidak ada web server
- State disimpan di JSON files (.ci_state.json, .ci_cookies.json)

---

## Folder `archive/`

Script lama untuk eksplorasi/probe. **TIDAK DIPAKAI** oleh sistem aktif. Berisi:
- `probe_auth.py`, `probe_session.py` — riset mekanisme auth SIMKULIAH
- `probe_login_fields.py` — cari field form login
- `probe_flash.py`, `probe_fallback.py/2.py` — test flash message
- `probe_msg.py`, `probe_struct.py`, `probe_links.py` — dump struktur halaman
- `dump_absensi.py`, `dump_jadwal.py`, `dump_js.py`, `dump_more.py`, `dump_aslab_table.py` — dump raw HTML
- `dump_clusters.py` — visualisasi cluster glyph
- `collect_gallery.py`, `eval_gallery.py`, `view_glyphs.py` — gallery tool glyph
- `oracle_test_tess.py`, `tess_test.py`, `oracle_tess2.py` — test Tesseract
- `charset_probe.py`, `font_match_probe.py`, `verify_probe.py` — probe karakter
- `hrefs.py` — dump semua href dari halaman

---

## Catatan untuk Model yang Mengedit Kode Ini

1. **Jangan ubah `config.py` tanpa cek semua importer** — hampir semua modul import dari sini
2. **CAPTCHA server consume-on-wrong** — JANGAN pernah multi-submit satu CAPTCHA
3. **`glyph_dict.json` ~3MB** — jangan load ulang berulang kali, singleton pattern sudah ada di `char_solver.get_solver()`
4. **`state_of()` di `tool.py` adalah ground truth** untuk klasifikasi status absensi
5. **`do_absen()` parsing bersifat heuristik** — jika SIMKULIAH ubah HTML, regex mungkin perlu update. Dump HTML halaman /absensi saat OPEN untuk debug: `python -c "import simkuliah; c=simkuliah.SIMKULIAH(); c.login('NIM','PASS'); print(c.get('/absensi').text)"`
6. **Telegram inline keyboard** — callback_data harus exact match: `'do_absen'` atau `'skip_absen'`
7. **Timezone** — semua waktu pakai WIB (Asia/Jakarta). Cron CI di UTC (offset -7 jam)
8. **CI cache key** menggunakan `run_id` → setiap run bikin cache baru, restore dari prefix
