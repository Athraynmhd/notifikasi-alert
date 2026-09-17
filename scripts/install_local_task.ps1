#Requires -Version 5.1
<#
.SYNOPSIS
  Install / update Windows Task Scheduler untuk absensi lokal.

.DESCRIPTION
  Task name: SIMKULIAH-Absensi-Notify
  Trigger: setiap 5 menit (script sendiri skip di luar Senin–Sabtu 07–19)
  Run whether user is logged on or not requires admin; default: when logged on.
#>

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root 'scripts\local_notify.ps1'
$TaskName = 'SIMKULIAH-Absensi-Notify'

if (-not (Test-Path $Script)) {
    throw "Script tidak ditemukan: $Script"
}

# Hapus task lama jika ada
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`"" `
    -WorkingDirectory $Root

# Tiap 5 menit, berulang tanpa batas; filter hari/jam di dalam script
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 12)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description 'SIMKULIAH absensi notify lokal (Telegram confirm). Skip Minggu & di luar 07-19.' `
    -Force | Out-Null

Write-Host "OK: Task '$TaskName' terpasang."
Write-Host "  Script : $Script"
Write-Host "  Root   : $Root"
Write-Host "  Jadwal : tiap 5 menit (filter Senin-Sabtu 07-19 di script)"
Write-Host ""
Write-Host "Tes sekarang:"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$Script`""
Write-Host "  Atau: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "Log: $Root\data\local_notify.log"
