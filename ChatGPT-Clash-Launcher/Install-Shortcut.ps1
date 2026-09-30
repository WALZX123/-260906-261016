$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$desktop=[Environment]::GetFolderPath('Desktop')
$destination=Join-Path $desktop 'ChatGPT（Clash代理）.lnk'
$backup=Join-Path $root ('desktop-backup-'+(Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Path $backup | Out-Null
foreach($name in @('ChatGPT.lnk','ChatGPT（Clash代理）.lnk')){
 $file=Join-Path $desktop $name
 if(Test-Path -LiteralPath $file){Copy-Item -LiteralPath $file -Destination $backup}
}
$pkg=Get-AppxPackage -Name OpenAI.Codex | Sort-Object {[version]$_.Version} -Descending | Select-Object -First 1
Copy-Item -LiteralPath (Join-Path $pkg.InstallLocation 'app\resources\icon-chatgpt.ico') -Destination (Join-Path $root 'ChatGPT.ico') -Force
$w=New-Object -ComObject WScript.Shell
$link=$w.CreateShortcut($destination)
$link.TargetPath="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$link.Arguments='-NoProfile -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File "'+$root+'\Launch-ChatGPT.ps1"'
$link.WorkingDirectory=$root
$link.IconLocation=(Join-Path $root 'ChatGPT.ico')+',0'
$link.Description='自动发现 Clash HTTP/Mixed 端口，以普通权限启动 ChatGPT；已有会话不会被关闭。'
$link.Save()
$verify=$w.CreateShortcut($destination)
[pscustomobject]@{Shortcut=$destination;Target=$verify.TargetPath;Arguments=$verify.Arguments;Backup=$backup} | ConvertTo-Json
