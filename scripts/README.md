# Scripts (bukan entry produksi)

| Folder / file | Isi | Contoh |
|---------------|-----|--------|
| `training/` | Kumpulkan/latih template CAPTCHA | `python scripts/training/harvest_labels.py 40` |
| `measure/` | Ukur akurasi solver | `python scripts/measure/test_opt.py` |
| `local_notify.ps1` | Runner lokal (Task Scheduler) | dijalankan otomatis tiap 5 menit |
| `local_notify_silent.vbs` | Launcher tanpa flash CMD | dipanggil task via `wscript //B` |
| `install_local_task.ps1` | Pasang task Windows (silent) | `powershell -File scripts/install_local_task.ps1` |

Jalankan **dari root repo** (`D:\learn\absen`). Tiap script Python memuat `scripts/repo_path.py` agar `import config` tetap jalan.

Entry produksi: `ci_notify.py`, `tool.py`.  
**Produksi harian:** Windows Task `SIMKULIAH-Absensi-Notify` (bukan cron GitHub — runner GH timeout ke SIMKULIAH).
