# CrabBots face-detection stage

## What runs

The project uses OpenCV's YuNet model (`face_detection_yunet_2023mar.onnx`) as its preferred detector. It returns face bounding boxes, five facial landmarks, and a detector score. The landmarks are needed by the downstream SFace alignment step.

If the YuNet model file is not installed, the standalone detection workflow falls back to OpenCV's bundled `haarcascade_frontalface_default.xml`. This fallback only detects frontal-face boxes. It deliberately reports no score and no landmarks, and `Detection.as_yunet_row()` refuses to convert it into SFace's alignment format. This prevents an approximate fallback from silently contaminating identity-recognition results.

## Run a still-image test

```bash
python scripts/detect_faces.py --image tests/fixtures/faces/Jack_Hathaway.jpg
```

The script reports the backend, number of faces, processing latency, and bounding boxes. It downsizes wide frames to 960 pixels for inference and maps returned boxes back to the original frame. It writes an annotated image to `data/face-detection-result.jpg` unless `--output` is specified.

## Run a webcam test

```bash
python scripts/detect_faces.py --camera 0 --seconds 20 --output data/camera-test.mp4
```

This processes every captured frame, overlays detected face boxes, and saves the result as MP4. Add `--display` only when using a GUI-enabled OpenCV build; the repository's default `opencv-python-headless` package intentionally has no desktop window support.

## Use the detector API

Start the application and open `/docs`:

- `GET /api/detection/status`
- `POST /api/detection/photo` with multipart form field `file`

The response contains `backend`, `face_count`, image dimensions, `latency_ms`, detections, and an `annotated_image` JPEG data URL. The endpoint does not invoke SFace, persist biometrics, create member records, or record attendance.

## Install the preferred YuNet model

```bash
python scripts/download_models.py --detection-only
```

The downloader checks the SHA-256 digest before installing the model. To install both YuNet and SFace for the full recognition pipeline, run `python scripts/download_models.py` without `--detection-only`.

## Limitations and next steps

- Haar fallback is a pragmatic local smoke-test path and is less robust than YuNet, especially for non-frontal faces, small faces, and challenging conditions.
- Detection is not recognition. It answers where a face appears in an image; SFace and the member gallery handle identity matching in the full pipeline.
- The included public-domain test portraits are smoke-test fixtures only. They do not establish accuracy for CrabBots members, webcam environments, or moving subjects.
- Next, benchmark YuNet on representative, consented images and video from the actual camera setup, then measure detection recall by face size, pose, lighting, and motion blur.
