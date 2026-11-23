# Nguyễn Tâm Bình - 2324801030003
# Chạy ở lần đăng nhập đầu: driver virtio + guest agent, cloudbase-init, bật RDP, dọn trạng thái để mỗi máy clone tự cấu hình lại, tắt máy
Start-Transcript -Path C:\Windows\Temp\tbt-setup.log
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$vw = (Get-Volume | Where-Object { $_.FileSystemLabel -like 'virtio-win*' }).DriveLetter
Start-Process "$($vw):\virtio-win-guest-tools.exe" -ArgumentList '/install', '/quiet', '/norestart' -Wait
Start-Process msiexec.exe -ArgumentList '/i', "`"$src\CloudbaseInitSetup_Stable_x64.msi`"", '/qn', '/norestart', '/l*v', 'C:\Windows\Temp\cbi-install.log', 'RUN_SERVICE_AS_LOCAL_SYSTEM=1', 'USERNAME=tbtadmin', 'USERGROUPS=Administrators', 'INJECTMETADATAPASSWORD=TRUE', 'LOGGINGSERIALPORTNAME=COM1' -Wait
Stop-Service cloudbase-init -Force -ErrorAction SilentlyContinue
$conf = 'C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf'
Copy-Item "$src\cloudbase-init.conf" $conf -Force
Set-Service cloudbase-init -StartupType Automatic
Set-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
Enable-NetFirewallRule -DisplayGroup 'Remote Desktop'
Enable-NetFirewallRule -Name 'FPS-ICMP4-ERQ-In' -ErrorAction SilentlyContinue
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
net user tbtadmin /delete 2>$null
Remove-Item 'HKLM:\SOFTWARE\Cloudbase Solutions\Cloudbase-Init' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item 'C:\Program Files\Cloudbase Solutions\Cloudbase-Init\log\*' -Force -ErrorAction SilentlyContinue
$ngau = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
net user Administrator $ngau /active:no
net user tbtbuild $ngau /active:no
Remove-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name DefaultPassword, AutoAdminLogon -ErrorAction SilentlyContinue
Stop-Transcript
Stop-Computer -Force
