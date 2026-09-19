"""Konfigurasi terpusat untuk SIMKULIAH security research tooling.

Semua konstanta, path, dan threshold didefinisikan di sini sebagai
satu sumber kebenaran. Modul lain cukup `from config import ...`.
"""

import os
import logging

# ──────────────────────────────────────────────────────────────
# URL & Network
# ──────────────────────────────────────────────────────────────
BASE_URL = 'https://simkuliah.usk.ac.id/index.php'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
REQUEST_TIMEOUT = 25  # detik

# ──────────────────────────────────────────────────────────────
# Tesseract OCR
# ──────────────────────────────────────────────────────────────
TESS_PATH = os.environ.get(
    'TESSERACT_PATH',
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
)
OCR_DIGIT_WHITELIST = '0123456789'
OCR_ALNUM_WHITELIST = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

# ──────────────────────────────────────────────────────────────
# CAPTCHA & Solver Thresholds
# ──────────────────────────────────────────────────────────────
CAPTCHA_CHAR_COUNT = 5
GLYPH_MIN_WIDTH = 6
GLYPH_MAX_WIDTH = 30
GLYPH_MAX_HEIGHT = 38
GLYPH_MAX_GLYPH_WIDTH = 26
STRENGTH_SAT_STRONG = 55
STRENGTH_LUM_STRONG = 175
STRENGTH_SAT_SOFT = 28
STRENGTH_LUM_SOFT = 200

# Template matching
CELL_H, CELL_W = 36, 24
IOU_CLUSTER_THRESHOLD = 0.50
SOLVER_MIN_CONF = 0.60

# Login
LOGIN_MAX_TRIES = 15
LOGIN_RETRY_DELAY = 0.3  # detik

# Ensemble: glyph di bawah SOLVER_MIN_CONF tapi ≥ ini tetap dicoba dulu
GLYPH_WEAK_CONF = 0.45

# ──────────────────────────────────────────────────────────────
# Data Directories (relatif terhadap project root)
# ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
TMP_DIR = os.path.join(DATA_DIR, 'tmp')
GLYPHS_DIR = os.path.join(DATA_DIR, 'glyphs')
META_JSON = os.path.join(DATA_DIR, 'glyph_meta.json')
ASSIGN_JSON = os.path.join(DATA_DIR, 'cluster_assign.json')
DICT_JSON = os.path.join(DATA_DIR, 'glyph_dict.json')
FONT_CACHE_NPZ = os.path.join(DATA_DIR, 'font_cache.npz')

os.makedirs(GLYPHS_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# Font Solver
# ──────────────────────────────────────────────────────────────
FONT_DIR = os.environ.get(
    'FONT_DIR',
    r'C:\Windows\Fonts' if os.name == 'nt' else '/usr/share/fonts',
)
CANDIDATE_FONTS = [
    'arialbd.ttf', 'arial.ttf', 'calibrib.ttf', 'calibri.ttf',
    'segoeuib.ttf', 'segoeui.ttf', 'seguisb.ttf', 'verdana.ttf',
    'verdanab.ttf', 'tahomabd.ttf', 'tahoma.ttf', 'consolab.ttf',
    'consola.ttf', 'georgiab.ttf', 'trebucbd.ttf', 'cambriab.ttf',
]
CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

# Telegram (bisa di-override CLI / env)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Gemini Vision CAPTCHA (primary solver)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash-lite').strip()
# gemini | local | auto  (auto = gemini dulu, fallback lokal)
CAPTCHA_SOLVER = os.environ.get('CAPTCHA_SOLVER', 'gemini').strip().lower()

# ──────────────────────────────────────────────────────────────
# Production: absen mode & alerting
# ──────────────────────────────────────────────────────────────
# confirm      → kirim tombol, tunggu respon Telegram
# auto         → absen langsung tanpa konfirmasi
# notify_only  → kabari saja, tidak absen
ABSEN_MODES = ('confirm', 'auto', 'notify_only')
ABSEN_MODE_DEFAULT = 'confirm'

# Alert login gagal: kirim saat streak pertama, lalu tiap N run berturut-turut
LOGIN_FAIL_ALERT_EVERY = int(os.environ.get('LOGIN_FAIL_ALERT_EVERY', '6'))

# Alert jika status parser UNKNOWN (kemungkinan HTML berubah)
PARSER_UNKNOWN_ALERT = os.environ.get('PARSER_UNKNOWN_ALERT', '1').strip().lower() not in (
    '0', 'false', 'no',
)

# Marker yang diharapkan di halaman /absensi (deteksi drift UI)
ABSENSI_MARKERS = (
    'belum masuk waktu absen',
    'btn-absen',
    'do_absen',
)


# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
LOG_DATE_FORMAT = '%H:%M:%S'


def setup_logging(level: int = logging.INFO) -> None:
    """Konfigurasi logging terpusat. Panggil sekali di entrypoint."""
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
