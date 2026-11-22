[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host ''
Write-Host 'CrabBots - one-time Windows setup' -ForegroundColor Cyan
Write-Host 'Run this before demo day while internet access is available.' -ForegroundColor Yellow
Write-Host ''

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw 'Python was not found on PATH. Install 64-bit Python 3.10, 3.11, 3.12, or 3.13, enable "Add Python to PATH", then rerun this script.'
}

$versionText = (& python --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $versionText -notmatch '^Python\s+(\d+)\.(\d+)') {
    throw "Could not determine the Python version. Command output: $versionText"
}
$pythonMajor = [int]$Matches[1]
$pythonMinor = [int]$Matches[2]
if ($pythonMajor -ne 3 -or $pythonMinor -lt 10 -or $pythonMinor -gt 13) {
    throw "CrabBots supports Python 3.10 through 3.13. Found: $versionText"
}
Write-Host "[OK] $versionText" -ForegroundColor Green

$venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host '[..] Creating the project virtual environment...'
    & python -m venv (Join-Path $RepoRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv.' }
} else {
    Write-Host '[OK] Existing .venv found.' -ForegroundColor Green
}

Write-Host '[..] Installing runtime dependencies (internet required for this setup step)...'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
& $venvPython -m pip install -r (Join-Path $RepoRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

Write-Host '[..] Downloading and checksum-verifying YuNet and SFace models...'
& $venvPython (Join-Path $RepoRoot 'scripts\download_models.py')
if ($LASTEXITCODE -ne 0) { throw 'Model download or checksum verification failed.' }

Write-Host '[..] Running local readiness checks...'
& (Join-Path $PSScriptRoot 'check_windows.ps1')

Write-Host ''
Write-Host 'CrabBots is prepared for offline use.' -ForegroundColor Green
Write-Host 'On demo day, run: .\scripts\run_windows.ps1' -ForegroundColor Green
Write-Host 'Do not delete .venv or the ONNX files in backend\models.' -ForegroundColor Yellow
