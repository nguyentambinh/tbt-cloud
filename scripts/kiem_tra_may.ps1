# Nguyễn Tâm Bình - 2324801030003
$ErrorActionPreference = 'SilentlyContinue'
$out = Join-Path ([Environment]::GetFolderPath('Desktop')) ("kiem_tra_may_" + $env:COMPUTERNAME + ".txt")
$lines = New-Object System.Collections.Generic.List[string]
function Add-Line($s) { $lines.Add($s); Write-Host $s }

$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1

Add-Line "=== THONG TIN MAY ==="
Add-Line "Ten may: $env:COMPUTERNAME"
Add-Line "Hang/Model: $($cs.Manufacturer) $($cs.Model)"
Add-Line "He dieu hanh: $($os.Caption) $($os.Version)"
Add-Line "CPU: $($cpu.Name) | Nhan: $($cpu.NumberOfCores) | Luong: $($cpu.NumberOfLogicalProcessors)"
Add-Line ("RAM: {0} GB" -f [math]::Round($cs.TotalPhysicalMemory / 1GB, 1))
Get-CimInstance Win32_DiskDrive | ForEach-Object { Add-Line ("O cung: {0} {1} GB" -f $_.Model, [math]::Round($_.Size / 1GB)) }
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | ForEach-Object { Add-Line ("O {0}: trong {1} GB / tong {2} GB" -f $_.Name, [math]::Round($_.Free / 1GB), [math]::Round(($_.Free + $_.Used) / 1GB)) }

Add-Line ""
Add-Line "=== AO HOA ==="
$hv = Get-Service vmcompute
Add-Line "VT bat trong BIOS: $($cpu.VirtualizationFirmwareEnabled) (False ma Hyper-V dang chay thi van la da bat)"
Add-Line "Dich vu Hyper-V (vmcompute): $(if ($hv) { $hv.Status } else { 'khong co' })"
$wsl = (wsl.exe -l -v 2>$null) -join ' ' -replace "`0", ''
Add-Line "WSL: $(if ($wsl) { $wsl } else { 'chua cai' })"

Add-Line ""
Add-Line "=== MANG ==="
Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | ForEach-Object { Add-Line "Card: $($_.InterfaceAlias) | IP LAN: $($_.IPv4Address.IPAddress) | Gateway: $($_.IPv4DefaultGateway.NextHop)" }
try { Add-Line ("IP public: " + (Invoke-RestMethod -Uri https://api.ipify.org -TimeoutSec 10)) } catch { Add-Line "IP public: khong lay duoc" }
$hops = tracert -d -h 3 -w 800 1.1.1.1 | Select-String '^\s+\d' | ForEach-Object { ($_ -split '\s+')[-2..-1] -join ' ' }
Add-Line ("3 chang dau: " + ($hops -join ' -> '))
$ping = Test-Connection 1.1.1.1 -Count 4
if ($ping) { Add-Line ("Ping 1.1.1.1 trung binh: {0} ms" -f [math]::Round(($ping | Measure-Object ResponseTime -Average).Average)) }

$lines | Out-File -FilePath $out -Encoding utf8
Write-Host ""
Write-Host "Da luu ket qua vao: $out  -> gui file nay cho nhom truong."
