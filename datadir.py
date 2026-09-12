"""Backward-compatible path constants — re-exported from config.py.

Modul lama yang `import datadir` tetap berjalan tanpa perubahan.
Untuk kode baru, gunakan `from config import DATA_DIR, TMP_DIR, ...` langsung.
"""

from config import (
    DATA_DIR as DATA,
    TMP_DIR as TMP,
    GLYPHS_DIR as GLYPHS,
    META_JSON as META,
    ASSIGN_JSON as ASSIGN,
    DICT_JSON,
)