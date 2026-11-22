[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& (Join-Path $PSScriptRoot 'check_windows.ps1')

$hostName = if ($env:CRABBOTS_HOST) { $env:CRABBOTS_HOST } else { '127.0.0.1' }
$port = if ($env:CRABBOTS_PORT) { [int]$env:CRABBOTS_PORT } else { 8000 }
if ($hostName -notin @('127.0.0.1', 'localhost')) {
    Write-Warning "CRABBOTS_HOST is set to '$hostName'. For a private single-computer demo, prefer 127.0.0.1."
}

$venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$uriHost = if ($hostName -eq '0.0.0.0') { '127.0.0.1' } else { $hostName }
$uri = "http://${uriHost}:$port"

$probe = [System.Net.Sockets.TcpClient]::new()
try {
    $probe.Connect($uriHost, $port)
    throw "Port $port is already in use. Close the other server or choose another CRABBOTS_PORT before starting CrabBots."
} catch [System.Net.Sockets.SocketException] {
    # Expected: no server is listening yet.
} finally {
    $probe.Dispose()
}

Write-Host ''
Write-Host 'Starting CrabBots locally. No downloads or installations will be attempted.' -ForegroundColor Cyan
Write-Host "Dashboard: $uri" -ForegroundColor Green
Write-Host 'Keep this window open. Press Ctrl+C to stop the server.' -ForegroundColor Yellow
Write-Host ''

$server = Start-Process -FilePath $venvPython -ArgumentList @('-m', 'backend.run') -WorkingDirectory $RepoRoot -PassThru -NoNewWindow
try {
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        if ($server.HasExited) {
            throw "CrabBots stopped during startup (exit code $($server.ExitCode))."
        }
        $client = [System.Net.Sockets.TcpClient]::new()
        try {
            $client.Connect($uriHost, $port)
            $ready = $true
            break
        } catch [System.Net.Sockets.SocketException] {
            Start-Sleep -Milliseconds 500
        } finally {
            $client.Dispose()
        }
    }
    if (-not $ready) { throw "CrabBots did not become ready at $uri within 20 seconds." }

    Start-Process $uri
    Wait-Process -Id $server.Id
} finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
}
