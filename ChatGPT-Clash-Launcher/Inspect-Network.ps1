$ErrorActionPreference='Stop'
. "$PSScriptRoot\Clash-Tools.ps1"
$proxy=Find-ClashProxy
$proxy | ConvertTo-Json
$live=Get-ClashApi '/configs'
$live | Select-Object mixed-port,port,socks-port,mode,@{n='TunEnabled';e={$_.tun.enable}} | ConvertTo-Json
$processes=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'ChatGPT.exe' -or ($_.Name -eq 'codex.exe' -and $_.CommandLine -match 'app-server') })
$ids=@($processes.ProcessId)
$tcp=@(Get-NetTCPConnection -State Established | Where-Object OwningProcess -in $ids)
$snapshot=Get-ClashApi '/connections'
$selected=@($snapshot.connections | Where-Object { [int]$_.metadata.sourcePort -in $tcp.LocalPort -or $_.metadata.processPath -match 'OpenAI.Codex.*ChatGPT.exe' } | ForEach-Object {
    [pscustomobject]@{id=$_.id;process=$_.metadata.process;processPath=$_.metadata.processPath;sourcePort=$_.metadata.sourcePort;host=$_.metadata.host;destinationPort=$_.metadata.destinationPort;type=$_.metadata.type;chains=$_.chains;upload=$_.upload;download=$_.download}
})
$selected | ConvertTo-Json -Depth 5
& curl.exe --proxy $proxy.Url --noproxy '' --connect-timeout 8 --max-time 20 --silent --show-error --output NUL --write-out 'http_connect=%{http_connect} http_code=%{http_code} ssl_verify_result=%{ssl_verify_result}\n' 'https://chatgpt.com/cdn-cgi/trace'
"curl_exit=$LASTEXITCODE"
