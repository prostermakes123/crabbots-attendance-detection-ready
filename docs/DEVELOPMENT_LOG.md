# Development log

## Base-code refinement — 2026-11-21

### Inspection
- Normalized the uploaded ZIP's Windows-style backslash paths into a conventional directory tree.
- Confirmed the Python modules compile before changes.
- Found that the source archive contained no collected pytest tests and no root README.
- Ran a baseline `pytest -q`; it exited with status 5 because no tests were collected.

### Fixes and improvements
- Fixed a correctness bug: `RecognitionPipeline.process_frame(record=False)` still wrote attendance and unknown-person events. Both persistence paths now honor the flag.
- Hardened embedding gallery inputs: rejects incompatible dimensions, zero vectors, and non-finite query vectors; malformed stored vectors are skipped with a warning.
- Validated member embeddings before writing member and embedding rows; normalized validated vectors and cleaned up a thumbnail if the database transaction fails.
- Hardened image data-URL parsing and checks encoded payload size before Base64 decoding.
- Serialized SFace alignment and feature extraction through the model lock.
- Added finite/positive video FPS and duration checks.
- Changed member image and video uploads to read in bounded chunks rather than buffering the entire upload without a limit check.
- Added WebSocket JSON-object validation and strict boolean handling for the `record` flag.
- Tightened settings updates: rejects unknown keys, invalid value types, incompatible threshold/margin values, and inverted brightness bounds.
- Constrained NumPy to `<2.3` to match the OpenCV 4.12 dependency range.
- Added pytest path configuration, a root README, and regression tests.

### Verification
- `python -m compileall -q backend scripts tests` — passed.
- `python -m pytest -q` — 11 passed.
- `node --check backend/app/static/app.js` — passed.
- FastAPI smoke test using a temporary SQLite database — `/`, `/api/health`, `/api/system/info`, and `/openapi.json` returned HTTP 200. Model files were absent, and the health endpoint correctly reported that model inference was not ready.

### Remaining work
- Download model weights and run real image/video inference tests on the target machine.
- Exercise the complete browser camera and enrollment workflow in a real browser.
- Add broader API/database integration tests and end-to-end UI tests.
- Complete authentication/authorization before any shared or network-accessible deployment.
- Calibrate recognition and tracking thresholds using representative, consented data; do not infer accuracy from synthetic footage.

## Face-detection milestone

- Added a standalone detector runtime that does not require the SFace identity model.
- Kept YuNet as the preferred face detector; added a clearly labeled OpenCV Haar frontal-face fallback so detection can be exercised before ONNX weights are installed.
- Added validation for image type, pixel depth, and score thresholds. Haar detections deliberately carry no confidence score or landmarks and cannot be converted into SFace alignment rows.
- Added `GET /api/detection/status` and `POST /api/detection/photo`, plus the `scripts/detect_faces.py` image/webcam runner.
- Added a detection-only option to the model downloader and documented the model download and smoke-test workflow.
- Verification: Python compilation, JavaScript syntax check, 19 automated tests, CLI inference on the bundled Jack Hathaway fixture, and API photo/status smoke tests.
- Environment limitation: network name resolution was unavailable in this execution environment, so the YuNet ONNX file could not be downloaded here. The Haar fallback was executed successfully. One false-positive box was observed on a non-face detail in the astronaut portrait, reinforcing that Haar is only a smoke-test fallback; validate YuNet with the intended webcam and consented test material before reporting detection performance.
