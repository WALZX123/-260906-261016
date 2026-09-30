Set-StrictMode -Version 2

function Get-ClashConfigFiles {
    $roots = @(
        (Join-Path $env:APPDATA 'io.github.clash-verge-rev.clash-verge-rev'),
        (Join-Path $env:APPDATA 'io.github.clash-verge.clash-verge'),
        (Join-Path $env:USERPROFILE '.config\clash'),
        (Join-Path $env:USERPROFILE '.config\mihomo'))
    foreach ($root in $roots) {
        foreach ($name in @('clash-verge.yaml','config.yaml')) {
            $path = Join-Path $root $name
            if (Test-Path -LiteralPath $path) { $path }
        }
    }
}

function Get-ClashApi([string]$Path) {
    $lastError = 'No controller pipe found.'
    foreach ($file in @(Get-ClashConfigFiles)) {
        $raw = Get-Content -LiteralPath $file -Raw
        $match = [regex]::Match($raw, '(?m)^external-controller-pipe:\s*(.+?)\s*$')
        if (-not $match.Success) { continue }
        $pipeName = $match.Groups[1].Value.Trim().Trim([char]39,[char]34) -replace '^\\\\\.\\pipe\\',''
        $actualPipes = @(Get-ChildItem -LiteralPath '\\.\pipe\' -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'verge-mihomo-*' })
        if ($actualPipes.Count -eq 1) { $pipeName = $actualPipes[0].Name }
        $secret = [regex]::Match($raw, '(?m)^secret:\s*(.*?)\s*$').Groups[1].Value.Trim().Trim([char]39,[char]34)
        $pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', $pipeName, [System.IO.Pipes.PipeDirection]::InOut, [System.IO.Pipes.PipeOptions]::Asynchronous)
        try {
            $pipe.Connect(1500)
            $auth = if ($secret) { "Authorization: Bearer $secret`r`n" } else { '' }
            $request = [Text.Encoding]::ASCII.GetBytes("GET $Path HTTP/1.1`r`nHost: localhost`r`n${auth}Connection: close`r`n`r`n")
            $pipe.Write($request, 0, $request.Length)
            $ms = New-Object IO.MemoryStream
            $buffer = New-Object byte[] 16384
            $deadline = [DateTime]::UtcNow.AddSeconds(5)
            while ([DateTime]::UtcNow -lt $deadline) {
                $task = $pipe.ReadAsync($buffer,0,$buffer.Length)
                if (-not $task.Wait(3000)) { throw 'Clash controller read timed out.' }
                $n = $task.Result
                if ($n -eq 0) { break }
                $ms.Write($buffer,0,$n)
                if ($ms.Length -gt 8388608) { throw 'Clash controller response too large.' }
            }
            $response = [Text.Encoding]::UTF8.GetString($ms.ToArray())
            $ms.Dispose()
            $split = $response.IndexOf("`r`n`r`n")
            if ($split -lt 0 -or $response -notmatch '^HTTP/1\.[01] 200') { throw 'Clash controller did not return HTTP 200.' }
            $body = $response.Substring($split+4)
            if ($response.Substring(0,$split) -match '(?i)Transfer-Encoding:\s*chunked') {
                # The controller uses UTF-8. Parse chunk lengths as bytes, not characters.
                $bytes = [Text.Encoding]::UTF8.GetBytes($body)
                $out = New-Object IO.MemoryStream
                $pos = 0
                while ($pos -lt $bytes.Length) {
                    $end = $pos
                    while ($end+1 -lt $bytes.Length -and -not ($bytes[$end] -eq 13 -and $bytes[$end+1] -eq 10)) { $end++ }
                    $line = [Text.Encoding]::ASCII.GetString($bytes,$pos,$end-$pos).Split(';')[0]
                    $size = [Convert]::ToInt32($line,16)
                    if ($size -eq 0) { break }
                    $pos = $end+2
                    $out.Write($bytes,$pos,$size)
                    $pos += $size+2
                }
                $body = [Text.Encoding]::UTF8.GetString($out.ToArray()); $out.Dispose()
            }
            return ($body | ConvertFrom-Json)
        } catch { $lastError = $_.Exception.Message }
        finally { $pipe.Dispose() }
    }
    throw "Cannot query Clash local controller: $lastError"
}

function Get-ClashListeners {
    $core = @(Get-Process -ErrorAction Stop | Where-Object { $_.ProcessName -match '^(verge-mihomo|mihomo|clash|clash-meta|clash-windows-amd64|clash-win64)([-.].*)?$' })
    if (-not $core.Count) { throw '未检测到运行中的 Clash/Mihomo 核心。请先打开 Clash 并启动代理。' }
    @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object {
        $_.OwningProcess -in $core.Id -and $_.LocalAddress -in @('127.0.0.1','0.0.0.0','::','::1')
    })
}

function Test-HttpProxy([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connect = $client.ConnectAsync('127.0.0.1',$Port)
        if (-not $connect.Wait(1800)) { throw 'TCP connection timed out.' }
        $stream = $client.GetStream(); $stream.ReadTimeout=7000; $stream.WriteTimeout=3000
        $bytes = [Text.Encoding]::ASCII.GetBytes("CONNECT chatgpt.com:443 HTTP/1.1`r`nHost: chatgpt.com:443`r`n`r`n")
        $stream.Write($bytes,0,$bytes.Length)
        $line = New-Object Text.StringBuilder
        while ($line.Length -lt 2048) {
            $ch=$stream.ReadByte(); if ($ch -lt 0 -or $ch -eq 10) { break }; [void]$line.Append([char]$ch)
        }
        if ($line.ToString() -notmatch '^HTTP/1\.[01] 200\b') { throw "HTTP CONNECT failed: $line" }
        return $line.ToString().Trim()
    } finally { $client.Dispose() }
}

function Find-ClashProxy([int]$OverridePort=0) {
    $listeners = @(Get-ClashListeners)
    $ports = New-Object 'System.Collections.Generic.List[int]'
    if ($OverridePort) { $ports.Add($OverridePort) }
    else {
        try {
            $live = Get-ClashApi '/configs'
            foreach ($key in @('mixed-port','port')) {
                if ($live.PSObject.Properties[$key] -and [int]$live.$key -gt 0) { $ports.Add([int]$live.$key) }
            }
        } catch { Write-Verbose $_.Exception.Message }
        foreach ($file in @(Get-ClashConfigFiles)) {
            foreach ($m in [regex]::Matches((Get-Content -LiteralPath $file -Raw),'(?m)^(?:mixed-port|port):\s*(\d+)')) { $ports.Add([int]$m.Groups[1].Value) }
        }
        foreach ($listener in $listeners) { $ports.Add([int]$listener.LocalPort) }
    }
    $failures=@()
    foreach ($candidate in @($ports | Select-Object -Unique)) {
        if ($candidate -notin $listeners.LocalPort) { $failures += "${candidate}: 没有 Clash 监听"; continue }
        try {
            $status = Test-HttpProxy $candidate
            return [pscustomobject]@{Port=$candidate;Url="http://127.0.0.1:$candidate";ConnectStatus=$status;CorePid=($listeners | Where-Object LocalPort -eq $candidate | Select-Object -First 1).OwningProcess}
        } catch { $failures += "${candidate}: $($_.Exception.Message)" }
    }
    throw "Clash 的 HTTP/Mixed 代理不可用。请检查 Clash 节点和端口。$($failures -join '; ')"
}

