[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$models = @(
    (Join-Path $RepoRoot 'backend\models\face_detection_yunet_2023mar.onnx'),
    (Join-Path $RepoRoot 'backend\models\face_recognition_sface_2021dec.onnx')
)

$missing = @()
if (-not (Test-Path $venvPython)) { $missing += '.venv\Scripts\python.exe (run scripts\setup_windows.ps1 before demo day)' }
foreach ($model in $models) {
    if (-not (Test-Path $model)) { $missing += $model }
}
if ($missing.Count -gt 0) {
    Write-Host 'CrabBots is not ready for offline use. Missing:' -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    throw 'CrabBots prerequisites are missing.'
}

Write-Host '[..] Checking local Python imports and loading both ONNX models...'
& $venvPython -c "import cv2, fastapi, multipart, numpy, pydantic, uvicorn; cv2.FaceDetectorYN.create(r'backend/models/face_detection_yunet_2023mar.onnx', '', (320, 320), 0.7, 0.3, 5000); cv2.FaceRecognizerSF.create(r'backend/models/face_recognition_sface_2021dec.onnx', ''); print('Dependencies and YuNet/SFace model loading OK; OpenCV', cv2.__version__)"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Python dependencies are incomplete. Run scripts\setup_windows.ps1 while internet is available.' -ForegroundColor Red
    throw 'CrabBots prerequisites are missing.'
}

Write-Host '[OK] Python environment and both ONNX models are present.' -ForegroundColor Green
Write-Host '[OK] This check does not access the internet.' -ForegroundColor Green
