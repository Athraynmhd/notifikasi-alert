#Requires -Version 5.1
<#
.SYNOPSIS
  Runner lokal absensi SIMKULIAH (pengganti cron GitHub Actions).

.DESCRIPTION
  - Skip otomatis di luar Senin–Sabtu 07:00–18:59 WIB
  - Load secrets dari .env di root repo
  - Jalankan ci_notify.py
  - Log ke data/local_notify.log

  Dipakai Task Scheduler: SIMKULIAH-Absensi-Notify
#>

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $Root 'ci_notify.py'))) {
    # fallback: script dijalankan dari root
    $Root = (Get-Location).Path
}

Set-Location $Root

# ---- jendela jam (WIB = local time PC Anda) ----
$now = Get-Date
$dow = [int]$now.DayOfWeek  # 0=Sunday .. 6=Saturday
if ($dow -eq 0) { exit 0 }  # Minggu off
$hour = $now.Hour
if ($hour -lt 7 -or $hour -ge 19) { exit 0 }

# ---- load .env ----
$envFile = Join-Path $Root '.env'
if (-not (Test-Path $envFile)) {
    Write-Error "File .env tidak ada di $Root — salin dari .env.example"
    exit 2
}

Get-Content $envFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $i = $line.IndexOf('=')
    if ($i -lt 1) { return }
    $k = $line.Substring(0, $i).Trim()
    $v = $line.Substring($i + 1).Trim()
    # strip optional quotes
    if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
        $v = $v.Substring(1, $v.Length - 2)
    }
    Set-Item -Path "Env:$k" -Value $v
}

$env:ABSEN_STATE_PATH = Join-Path $Root '.ci_state.json'
$env:ABSEN_COOKIES_PATH = Join-Path $Root '.ci_cookies.json'
if (-not $env:TESSERACT_PATH) {
    $env:TESSERACT_PATH = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
}
if (-not $env:ABSEN_MODE) { $env:ABSEN_MODE = 'confirm' }

$Python = $env:ABSEN_PYTHON
if (-not $Python) {
    $candidates = @(
        'C:\Program Files\Python310\python.exe',
        'C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe',
        'C:\Python312\python.exe',
        'python'
    )
    foreach ($c in $candidates) {
        if ($c -eq 'python') { $Python = 'python'; break }
        if (Test-Path $c) { $Python = $c; break }
    }
}

$logDir = Join-Path $Root 'data'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir 'local_notify.log'

function Write-Log([string]$msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-Log "START python=$Python mode=$($env:ABSEN_MODE)"
try {
    $p = Start-Process -FilePath $Python -ArgumentList 'ci_notify.py' `
        -WorkingDirectory $Root -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir 'local_notify_stdout.txt') `
        -RedirectStandardError (Join-Path $logDir 'local_notify_stderr.txt')
    $code = $p.ExitCode
    Write-Log "END exit=$code"
    # append stdout/stderr tails to main log
    foreach ($f in @('local_notify_stdout.txt', 'local_notify_stderr.txt')) {
        $fp = Join-Path $logDir $f
        if (Test-Path $fp) {
            Get-Content $fp -ErrorAction SilentlyContinue | ForEach-Object { Add-Content $logFile $_ -Encoding UTF8 }
        }
    }
    exit $code
} catch {
    Write-Log "ERROR $_"
    exit 1
}
