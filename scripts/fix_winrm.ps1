# =====================================================================
# fix_winrm.ps1 — 在 Windows 主机上以管理员运行一次，永久搞定 WinRM 监控
#
# 用途:
#   ops-relay 通过 WinRM(5985) 监控 Windows。断电重启后若失联，通常是
#   WinRM 服务没自启 / 防火墙在网络变 Public 时没放通 / 认证方式没开。
#   本脚本一次解决并把配置做成重启持久。
#
# 用法: 右键 PowerShell "以管理员身份运行"，然后:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\fix_winrm.ps1
#
# 跑完后 ops-relay 那边用 ansible_connection=winrm + transport=ntlm/basic 都能连。
# =====================================================================

#Requires -RunAsAdministrator
$ErrorActionPreference = 'Continue'

Write-Host "==> 1/7 启动并设置 WinRM 服务为自动" -ForegroundColor Cyan
Set-Service -Name WinRM -StartupType Automatic
Start-Service -Name WinRM

Write-Host "==> 2/7 基础配置 (winrm quickconfig)" -ForegroundColor Cyan
winrm quickconfig -quiet -force | Out-Null

Write-Host "==> 3/7 开启 NTLM + Basic 认证（兼容 ansible ntlm/basic transport）" -ForegroundColor Cyan
winrm set winrm/config/service/Auth '@{Basic="true"; Negotiate="true"; CredSSP="false"}' | Out-Null
winrm set winrm/config/client/Auth '@{Basic="true"; Negotiate="true"}' | Out-Null

Write-Host "==> 4/7 允许 HTTP 明文（basic over http 需要）" -ForegroundColor Cyan
winrm set winrm/config/service '@{AllowUnencrypted="true"}' | Out-Null
winrm set winrm/config/client '@{AllowUnencrypted="true"; TrustedHosts="*"}' | Out-Null

Write-Host "==> 5/7 防火墙：所有配置文件(含 Public)永久放通 5985（重启/断电后网络变 Public 也不挡）" -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName "ops-relay WinRM-HTTP-In" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName "ops-relay WinRM-HTTP-In" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5985 `
    -Profile Any -Enabled True | Out-Null

Write-Host "==> 6/7 把当前网络设为 Private（尽量避免重启后被识别为 Public）" -ForegroundColor Cyan
Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' } |
    Set-NetConnectionProfile -NetworkCategory Private

Write-Host "==> 7/7 自检" -ForegroundColor Cyan
$svc = Get-Service WinRM
$listener = (winrm enumerate winrm/config/listener 2>$null | Select-String "Transport = HTTP").Count
Write-Host ("WinRM 服务: {0} ({1})" -f $svc.Status, $svc.StartType)
Write-Host ("HTTP 监听(5985): {0}" -f $(if ($listener -gt 0) {'已监听'} else {'未监听!'}))
Test-NetConnection -ComputerName 127.0.0.1 -Port 5985 -InformationLevel Quiet |
    ForEach-Object { Write-Host ("本地 5985 连通: {0}" -f $_) }

Write-Host ""
Write-Host "完成。此机已被 ops-relay 纳管，且配置重启持久。" -ForegroundColor Green
Write-Host "若 ansible 仍连不上，检查 administrator 密码是否与 inventory.ini 一致。" -ForegroundColor Yellow
