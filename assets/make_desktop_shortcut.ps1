$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'Tax Agent.lnk'
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = 'C:\Users\yusun\projects\tax-agent\dist\TaxAgent.exe'
$lnk.IconLocation = 'C:\Users\yusun\projects\tax-agent\assets\icon.ico,0'
$lnk.WorkingDirectory = 'C:\Users\yusun\projects\tax-agent'
$lnk.WindowStyle = 7
$lnk.Description = 'Tax Agent - Local AI Tax Assistant'
$lnk.Save()
Write-Host "created: $lnkPath"
Get-Item $lnkPath | Select-Object Name, Length, LastWriteTime | Format-List
