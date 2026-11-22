# CrabBots Attendance

A local-first attendance application built with FastAPI, OpenCV YuNet face detection, OpenCV SFace embeddings, a SQLite member/attendance store, and a browser-based live camera dashboard.

> **Biometric notice:** this application processes biometric identifiers. Use it only with informed, documented consent and in accordance with applicable law and CrabBots policy. The included NASA portraits are public-domain demo fixtures, not CrabBots members. Do not enroll people from the fixtures as real attendees.

## Requirements

- Python 3.10–3.13
- A webcam for live recognition (optional; photo recognition and the rest of the UI can be explored without one)
- Internet access only for the initial model download and optional demo/evaluation datasets

## Quick start

```bash
# From the repository root
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python scripts/download_models.py
python -m backend.run
```

Open <http://127.0.0.1:8000>. The first model load may take a few seconds. Camera access is supported on `localhost` and secure HTTPS origins; use `http://localhost:8000` rather than a LAN IP for a local browser demo unless HTTPS is configured.

The ONNX model files are downloaded into `backend/models/` and are intentionally excluded from Git. `scripts/download_models.py` verifies their SHA-256 checksums before installing them.

## Configuration

Copy `.env.example` to `.env` to override defaults:

| Variable | Default | Purpose |
|---|---|---|
| `CRABBOTS_DB_PATH` | `data/crabbots.db` | SQLite database path |
| `CRABBOTS_MODEL_DIR` | `backend/models` | ONNX model directory |
| `CRABBOTS_ADMIN_TOKEN` | empty | Protects selected administrative mutations when configured |
| `CRABBOTS_HOST` | `127.0.0.1` | Bind address |
| `CRABBOTS_PORT` | `8000` | HTTP port |
| `CRABBOTS_LOG_LEVEL` | `INFO` | Logging level |

Keep the server bound to localhost for a single-machine demo. The empty admin token is a local-demo convenience, not an appropriate shared-deployment security configuration. Before exposing the application to a network, add authentication/authorization for all mutating and biometric endpoints, HTTPS, access controls, secure backups, and a retention/deletion policy. Do not treat the current local-demo UI as an authorization boundary.

## Tests and checks

```bash
python -m compileall -q backend scripts tests
python -m pytest -q
node --check backend/app/static/app.js  # optional; requires Node.js
```

Tests exercise image decoding/validation, embedding gallery behavior, tracking, and the non-recording pipeline mode. They do not replace evaluation against consented real-world video or verify recognition accuracy for a particular population or camera setup.

## Optional demo and evaluation data

```bash
python scripts/fetch_demo_faces.py
python scripts/fetch_demo_faces.py --fixtures
python scripts/make_motion_clip.py --image tests/fixtures/faces/Jack_Hathaway.jpg --out data/demo/walk_past.mp4
```

Demo portraits are labeled as demo data and must not be represented as real CrabBots attendance. The synthetic motion clip is useful for exercising the video path but does not establish real-world moving-face recognition accuracy.

For an optional LFW evaluation cache:

```bash
python scripts/fetch_lfw_subset.py --rows 1200
python scripts/evaluate.py --pairs 400
```

LFW is an evaluation dataset, not enrollment data. Review its terms and the mirror's provenance before use. Record dataset scope and limitations alongside any reported metrics.

## Architecture

- `backend/app/api/` — HTTP and WebSocket routes
- `backend/app/services/` — detection, recognition, tracking, gallery, enrollment, and attendance logic
- `backend/app/db/` — SQLite schema and data access
- `backend/app/static/` — browser UI
- `scripts/` — model/data utilities and evaluation scripts
- `tests/` — automated regression tests

The browser captures camera frames and sends compressed frames to `/ws/live`. The server detects faces, creates SFace embeddings, matches them against the in-memory gallery, aggregates evidence per track, and writes attendance events through the attendance service. The gallery is loaded from SQLite at startup and updated after enrollment/deletion.

## Known limitations

- The included YuNet/SFace models are a practical CPU-friendly baseline, not a guarantee of reliable identification under every lighting, pose, demographic, or movement condition.
- The IoU tracker is lightweight and may lose identity continuity during heavy occlusion, rapid motion, or crossing trajectories.
- Recognition thresholds must be calibrated on representative, consented data for the actual deployment environment. Similarity is not a probability of identity.
- Local SQLite and a single-process in-memory gallery are suitable for a local demo, not multi-instance production deployment.
- A configured admin token currently protects selected administrative endpoints only. A production deployment needs a complete authentication and authorization design.

## License and model terms

Review the repository license (if added) and the individual licenses/terms for code, model weights, demo images, and evaluation data before redistribution or deployment. The model downloader records the intended upstream model licenses; verify upstream terms at the time you use or redistribute the models.

## Face detection smoke test (works without SFace)

The face detector can now be run independently from identity recognition. This is useful while developing the camera/detection stage before installing the larger SFace embedding model.

```bash
# Download only YuNet (~233 KB) for the preferred detector
python scripts/download_models.py --detection-only

# Detect faces in a test image and save an annotated copy
python scripts/detect_faces.py --image tests/fixtures/faces/Jack_Hathaway.jpg

# Or choose the output filename
python scripts/detect_faces.py --image path/to/photo.jpg --output data/face-result.jpg

# Process a webcam for 20 seconds and save an annotated MP4
python scripts/detect_faces.py --camera 0 --seconds 20 --output data/camera-test.mp4
```

If YuNet weights are not present, the standalone detector automatically uses OpenCV's bundled `haarcascade_frontalface_default.xml` as a **frontal-face detection fallback**. Haar fallback can return bounding boxes, but it does not return facial landmarks or a calibrated confidence score. It is intended only to prove and exercise the detection stage; it is not used for SFace alignment or identity recognition. YuNet is preferred for normal operation. The full recognition pipeline still requires both YuNet and SFace:

```bash
python scripts/download_models.py
```

The application also exposes a detector-only API that does not require SFace:

- `GET /api/detection/status` — reports the active detection backend.
- `POST /api/detection/photo` — upload an image as multipart form field `file`; returns face boxes, available landmarks, timing, and a base64 annotated preview.

These routes do not enroll people, identify anyone, or write attendance records. Use `/docs` on the local server to try them interactively.


## Windows host-computer demo (prepare once, run offline on demo day)

The repository includes Windows scripts for a host computer that must run the presentation without downloading anything during the demo. **The host must be prepared in advance while internet access is available.** A fresh clone alone does not include Python packages or ONNX model weights.

### One-time preparation before demo day

Install 64-bit Python 3.10–3.13 and Git for Windows, then clone this repository on the host computer:

```powershell
git clone https://github.com/prostermakes123/crabbots-attendance-detection-ready.git
cd crabbots-attendance-detection-ready
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

The setup script creates `.venv`, installs the runtime packages from `requirements.txt`, downloads YuNet and SFace, verifies both model SHA-256 checksums, and runs a local readiness check. Confirm that it reports **prepared for offline use**. You can run `.\scripts\check_windows.ps1` any time to verify the local prerequisites; that check does not access the internet.

### On demo day

Double-click `START-CRABBOTS.bat`, or run:

```powershell
.\scripts\run_windows.ps1
```

The launcher checks the already-installed environment and local model files, starts the app, and opens the local dashboard. It does **not** run Git, pip, or the model downloader and does not need internet access. Keep the terminal open while demonstrating; press `Ctrl+C` to stop the server.

Do not delete `.venv` or the two files in `backend\models` after preparation. If the repository is updated, run `git pull` and `.\scripts\setup_windows.ps1` before demo day, not during the presentation. Full instructions and troubleshooting are in [`docs/WINDOWS_DEMO_SETUP.md`](docs/WINDOWS_DEMO_SETUP.md).
