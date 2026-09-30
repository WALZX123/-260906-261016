[CmdletBinding()]
param([switch]$CheckOnly,[switch]$NoPopup)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$logs=Join-Path $root 'logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$log=Join-Path $logs ('launch-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.log')
function Write-Log([string]$Message) { ('[{0}] {1}' -f (Get-Date -Format s),$Message) | Tee-Object -FilePath $log -Append | Write-Host }
function Notify([string]$Message) {
 Write-Log $Message
 if(-not $NoPopup){Add-Type -AssemblyName System.Windows.Forms; [void][Windows.Forms.MessageBox]::Show($Message+"`r`n`r`n日志："+$log,'ChatGPT · Clash 代理启动')}
}
try {
 $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
 if($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw '请以普通用户双击入口，不要以管理员身份运行。'}
 . "$root\Clash-Tools.ps1"
 $config=Get-Content -LiteralPath "$root\launcher.json" -Raw | ConvertFrom-Json
 if([int]$config.Port -lt 0 -or [int]$config.Port -gt 65535){throw '端口必须为 0（自动）或 1–65535。'}
 $pkg=Get-AppxPackage -Name $config.PackageName | Sort-Object {[version]$_.Version} -Descending | Select-Object -First 1
 if(-not $pkg){throw '未找到已注册的 ChatGPT 应用包。请从 Microsoft Store 安装或修复 ChatGPT 后重试。'}
 [xml]$manifest=Get-Content -LiteralPath (Join-Path $pkg.InstallLocation 'AppxManifest.xml') -Raw
 $app=@($manifest.Package.Applications.Application) | Where-Object Id -eq 'App' | Select-Object -First 1
 $exe=Join-Path $pkg.InstallLocation $app.Executable
 if(-not (Test-Path -LiteralPath $exe)){throw "找不到应用程序：$exe"}
 Write-Log "Package=$($pkg.PackageFullName); Executable=$exe"
 $proxy=Find-ClashProxy ([int]$config.Port)
 Write-Log "Clash PID=$($proxy.CorePid); Proxy=$($proxy.Url); CONNECT=$($proxy.ConnectStatus)"
 # Explicit proxy probe, certificate validation remains enabled.
 $request=[Net.HttpWebRequest]::Create('https://chatgpt.com/cdn-cgi/trace')
 $request.Proxy=New-Object Net.WebProxy($proxy.Url)
 $request.Timeout=15000
 try {$response=$request.GetResponse(); Write-Log "HTTPS test=$([int]$response.StatusCode)"; $response.Close()}
 catch [Net.WebException] {if($_.Exception.Response){Write-Log "HTTPS reachable; HTTP=$([int]$_.Exception.Response.StatusCode)"; $_.Exception.Response.Close()}else{throw}}
 $existing=@(Get-CimInstance Win32_Process -Filter "Name='ChatGPT.exe'" | Where-Object { $_.ExecutablePath -eq $exe -and $_.CommandLine -notmatch '--type=' -and $_.CommandLine -notmatch 'ChatGPT-Clash-Launcher\\(?:activation-test-profile|probe-profile)' })
 if($CheckOnly){Write-Log "检查完成；现有主进程数=$($existing.Count)。未启动或关闭应用。"; exit 0}
 if($existing.Count){
  $desired='--proxy-server='+$proxy.Url
  if(@($existing | Where-Object { $_.CommandLine -like "*$desired*" }).Count){Notify 'ChatGPT 已使用本次代理参数运行，请切换到现有窗口。'}
  else{Notify 'ChatGPT 已在运行，本次没有更改现有进程。请先保存工作，等待 Agent 任务结束，在 ChatGPT 中正常退出（仅关闭窗口可能仍驻留），然后再次双击此入口。当前已有 TUN 代理不代表新启动参数已生效。'}
  exit 2
 }
 . "$root\Activate-App.ps1"
 $arguments='--proxy-server='+$proxy.Url+' --disable-quic'
 $appId=$pkg.PackageFamilyName+'!'+$app.Id
 Write-Log "Activation=$appId; Arguments=$arguments"
 $targetId=[ClashLauncher.Activator]::Launch($appId,$arguments)
 Write-Log "Windows activation returned PID=$targetId"
 Start-Sleep -Seconds 5
 $process=Get-CimInstance Win32_Process -Filter "ProcessId=$targetId"
 if(-not $process){throw '应用激活后进程已退出。请查看本日志及 Windows 应用部署日志。'}
 Write-Log "Process alive; CommandLine=$($process.CommandLine)"
 if($process.CommandLine -notlike "*--proxy-server=$($proxy.Url)*"){throw '进程存在，但未确认代理参数被接收；不要视为代理启动成功。'}
 Write-Log '已确认启动成功并携带代理参数。开始检查实际连接。'
 $confirmed=$false
 for($i=0;$i -lt 8;$i++){
  $ps=@(Get-CimInstance Win32_Process -Filter "Name='ChatGPT.exe'" | Where-Object ExecutablePath -eq $exe)
  $tcp=@(Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $ps.ProcessId -and $_.RemoteAddress -eq '127.0.0.1' -and $_.RemotePort -eq $proxy.Port })
  if($tcp.Count){
   Write-Log "已确认目标应用 TCP 连接到 Clash 代理端口，源端口=$($tcp.LocalPort -join ',')"
   try {$connections=(Get-ClashApi '/connections').connections; foreach($c in @($connections | Where-Object { [int]$_.metadata.sourcePort -in $tcp.LocalPort -and $_.metadata.type -match 'HTTP' })) {Write-Log "Clash HTTP flow: host=$($c.metadata.host); type=$($c.metadata.type); upload=$($c.upload); download=$($c.download)"; $confirmed=$true}}catch{Write-Log "Clash 流量查询失败：$($_.Exception.Message)"}
   if($confirmed){break}
  }
  Start-Sleep -Seconds 2
 }
 if(-not $confirmed){Write-Log '尚未捕获 Clash HTTP 请求记录；启动和参数已确认，但不能据此宣称所有网络流量经过代理。'}
} catch {
 $failureMessage=$_.Exception.Message
 $detail=($_ | Out-String)+"`r`n"+$_.ScriptStackTrace
 Write-Log $detail
 try {Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppXDeploymentServer/Operational';StartTime=(Get-Date).AddMinutes(-5)} -MaxEvents 40 -ErrorAction Stop | Where-Object { $_.Message -match 'OpenAI|80073D28' } | Format-List TimeCreated,Id,Message | Out-String | Add-Content -LiteralPath $log}catch{}
 Notify ('启动未完成：'+$failureMessage+"`r`n若出现 0x80073D28，请先检查已保存的部署日志；本程序不会自动提权、重新注册应用或修改 WindowsApps 权限。")
 exit 1
}
