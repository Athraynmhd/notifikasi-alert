#Requires -Version 5.1
<#
.SYNOPSIS
  Install / update Windows Task Scheduler untuk absensi lokal (silent).

.DESCRIPTION
  Task name: SIMKULIAH-Absensi-Notify
  Trigger: setiap 1 menit (script sendiri skip di luar Senin–Sabtu 07–19)
  Launcher: wscript + VBS (tanpa flash CMD/PowerShell)
#>

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Vbs = Join-Path $Root 'scripts\local_notify_silent.vbs'
$Ps1 = Join-Path $Root 'scripts\local_notify.ps1'
$TaskName = 'SIMKULIAH-Absensi-Notify'

if (-not (Test-Path $Vbs)) { throw "VBS tidak ditemukan: $Vbs" }
if (-not (Test-Path $Ps1)) { throw "Script tidak ditemukan: $Ps1" }

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# wscript //B = batch mode (no script errors UI); VBS Run style 0 = hidden
$action = New-ScheduledTaskAction `
    -Execute 'wscript.exe' `
    -Argument "//B `"$Vbs`"" `
    -WorkingDirectory $Root

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 12) `
    -Hidden

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
    -Description 'SIMKULIAH absensi notify lokal (silent, 1 menit). Hanya Kamis/Jumat/Sabtu sesuai jadwal_windows.json.' `
    -Force | Out-Null

Write-Host "OK: Task '$TaskName' silent terpasang (interval 1 menit)."
Write-Host "  Launcher: $Vbs"
Write-Host "  Script  : $Ps1"
