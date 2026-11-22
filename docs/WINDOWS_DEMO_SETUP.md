# Windows host-computer setup and offline demo

This procedure is designed for a Windows 10/11 computer that can be prepared before the interview. **The demo-day launch does not install packages, download models, call GitHub, or require internet access.** The host must be prepared in advance.

## Before demo day (one-time preparation, internet required)

1. Install 64-bit Python 3.10, 3.11, 3.12, or 3.13 and Git for Windows on the host computer.
2. Open PowerShell and clone this repository:

   ```powershell
   git clone https://github.com/prostermakes123/crabbots-attendance-detection-ready.git
   cd crabbots-attendance-detection-ready
   ```

3. Run the setup script. It creates `.venv`, installs the runtime requirements, downloads both ONNX models, verifies their SHA-256 checksums, and runs a local readiness check:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\scripts\setup_windows.ps1
   ```

4. Confirm that the final message says the project is prepared for offline use. You can also run:

   ```powershell
   .\scripts\check_windows.ps1
   ```

5. Open the dashboard once and verify the camera permission prompt in Chrome or Edge. Use the local address `http://127.0.0.1:8000`.

## On demo day (no internet required)

1. Do not delete the repository's `.venv` directory or either model file in `backend\models`.
2. Double-click `START-CRABBOTS.bat`, or run:

   ```powershell
   .\scripts\run_windows.ps1
   ```

3. The launcher checks the local Python environment and model files, starts the FastAPI server, waits for it to respond, and opens the browser. It does not run `pip`, the model downloader, `git`, or any network download.
4. Keep the terminal open while demonstrating; press `Ctrl+C` to stop it.

## Updating the project before the interview

Pull code updates and rerun setup **before** demo day, while internet is available:

```powershell
git pull
.\scripts\setup_windows.ps1
```

If `requirements.txt` or the model downloader changes, rerunning setup refreshes the local environment and verifies model files. Do not depend on `git pull` or setup during the live demonstration.

## Troubleshooting

- **Python not found:** install 64-bit Python 3.10–3.13 and enable the Python PATH option, then rerun setup.
- **Model missing:** run `scripts\setup_windows.ps1` while internet is available. The test-day launcher deliberately fails rather than attempting a download.
- **Port 8000 is occupied:** close the other local server, or set `CRABBOTS_PORT` before launching and open the matching localhost URL.
- **Camera not listed:** check Windows camera privacy settings and browser permissions. Use `localhost`/`127.0.0.1`, not an unsecured LAN address.
- **Do not copy personal member photos, biometric embeddings, `.env` secrets, or the local database into the public repository.** The app's local `data` directory is intentionally ignored by Git.

## What is stored where

- Source and tests: GitHub repository.
- Python runtime dependencies: the host computer's `.venv` directory, created before demo day.
- YuNet and SFace ONNX model files: `backend\models`, downloaded and checksum-verified before demo day; excluded from ordinary Git commits.
- Local attendance database and member data: `data`, kept on the host computer and excluded from Git.

This is a pre-provisioned source checkout, not a claim that a fresh `git clone` can run offline without preparation. The host computer must complete the one-time setup before the offline demonstration.
