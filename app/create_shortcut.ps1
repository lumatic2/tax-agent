$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Tax Agent.lnk")
$Shortcut.TargetPath = "$env:USERPROFILE\projects\local-ai-workstation\dist\TaxAgent.exe"
$Shortcut.WorkingDirectory = "$env:USERPROFILE\projects\local-ai-workstation\dist"
$Shortcut.IconLocation = "$env:USERPROFILE\projects\local-ai-workstation\assets\icon.ico,0"
$Shortcut.Description = "Tax Agent - 소득세 계산 · 절세 분석"
$Shortcut.Save()
Write-Host "Shortcut created: $env:USERPROFILE\Desktop\Tax Agent.lnk"
