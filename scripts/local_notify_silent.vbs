' Silent launcher for SIMKULIAH local notify — no console flash.
' Called by Task Scheduler every 5 minutes.
Option Explicit
Dim sh, root, ps1, cmd
Set sh = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(root)
ps1 = root & "\scripts\local_notify.ps1"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
' 0 = hidden window, False = don't wait
sh.Run cmd, 0, False
