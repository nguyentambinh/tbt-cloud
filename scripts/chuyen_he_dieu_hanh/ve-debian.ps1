# Nguyễn Tâm Bình - 2324801030003
# Chay bang PowerShell (Admin): powershell -ExecutionPolicy Bypass -File C:\TBT\ve-debian.ps1
$ErrorActionPreference = "Stop"
$ds = (bcdedit /enum firmware) -join "`n"
$khoi = $ds -split "`n`n" | Where-Object { $_ -match "description\s+debian" } | Select-Object -First 1
if (-not $khoi) { Write-Host "Khong tim thay muc khoi dong debian trong UEFI." -ForegroundColor Red; exit 1 }
$id = [regex]::Match($khoi, "identifier\s+(\{[0-9a-fA-F-]+\})").Groups[1].Value
bcdedit /set "{fwbootmgr}" bootsequence $id | Out-Null
Write-Host "Lan khoi dong ke tiep vao Debian/Proxmox ($id). Khoi dong lai sau 10 giay..." -ForegroundColor Green
shutdown /r /t 10
