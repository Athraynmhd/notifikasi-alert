# Scripts (bukan entry produksi)

| Folder | Isi | Contoh |
|--------|-----|--------|
| `training/` | Kumpulkan/latih template CAPTCHA | `python scripts/training/harvest_labels.py 40` |
| `measure/` | Ukur akurasi solver | `python scripts/measure/test_opt.py` |

Jalankan **dari root repo** (`D:\learn\absen`). Tiap script memuat `scripts/repo_path.py` agar `import config` tetap jalan.

Entry produksi tetap di root: `ci_notify.py`, `tool.py`.
