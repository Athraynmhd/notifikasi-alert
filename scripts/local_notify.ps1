#Requires -Version 5.1
<#
.SYNOPSIS
  Runner lokal absensi SIMKULIAH — hanya di jendela jam kuliah Anda.

.DESCRIPTION
  - Skip kecuali Kamis/Jumat/Sabtu sesuai data/jadwal_windows.json (+ buffer)
  - Load secrets dari .env
  - Jalankan ci_notify.py
  - Log ke data/local_notify.log

  Task: SIMKULIAH-Absensi-Notify (tiap 1 menit, silent)
#>

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $Root 'ci_notify.py'))) {
    $Root = (Get-Location).Path
}
Set-Location $Root

function Get-Minutes([string]$hhmm) {
    $p = $hhmm.Split(':')
    return ([int]$p[0]) * 60 + [int]$p[1]
}

function Test-InClassWindow {
    $path = Join-Path $Root 'data\jadwal_windows.json'
    if (-not (Test-Path $path)) { return $false }
    $cfg = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $buffer = 15
    if ($null -ne $cfg.buffer_menit) { $buffer = [int]$cfg.buffer_menit }

    $now = Get-Date
    $dow = [int]$now.DayOfWeek  # 0=Minggu .. 6=Sabtu
    $nowMin = $now.Hour * 60 + $now.Minute

    foreach ($w in $cfg.windows) {
        if ([int]$w.dow -ne $dow) { continue }
        $start = (Get-Minutes ([string]$w.start)) - $buffer
        $end = Get-Minutes ([string]$w.end)
        if ($nowMin -ge $start -and $nowMin -le $end) {
            return $true
        }
    }
    return $false
}

# ---- gate: hanya jam kuliah Anda ----
if (-not (Test-InClassWindow)) {
    exit 0
}

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

Write-Log "START in-window python=$Python mode=$($env:ABSEN_MODE)"
try {
    $p = Start-Process -FilePath $Python -ArgumentList 'ci_notify.py' `
        -WorkingDirectory $Root -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir 'local_notify_stdout.txt') `
        -RedirectStandardError (Join-Path $logDir 'local_notify_stderr.txt')
    $code = $p.ExitCode
    Write-Log "END exit=$code"
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
