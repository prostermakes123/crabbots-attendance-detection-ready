"""Download the two ONNX models used by the pipeline.

Both are small, CPU-friendly and permissively licensed:
  * YuNet face detector  - MIT      (opencv/opencv_zoo)
  * SFace face recogniser - Apache-2.0 (opencv/opencv_zoo)

Run from the repository root:  python scripts/download_models.py
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "backend" / "models"

MODELS = [
    {
        "name": "face_detection_yunet_2023mar.onnx",
        "url": "https://huggingface.co/opencv/opencv_zoo/resolve/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "license": "MIT",
        "size_mb": 0.2,
    },
    {
        "name": "face_recognition_sface_2021dec.onnx",
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "license": "Apache-2.0",
        "size_mb": 38.7,
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(model: dict) -> None:
    target = MODEL_DIR / model["name"]
    if target.is_file() and sha256(target) == model["sha256"]:
        print(f"[ok] {model['name']} already present and verified")
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")
    print(f"[..] downloading {model['name']} ({model['size_mb']} MB, {model['license']})")
    request = urllib.request.Request(model["url"], headers={"User-Agent": "CrabBots-Attendance/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response, tmp.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    actual = sha256(tmp)
    if actual != model["sha256"]:
        tmp.unlink(missing_ok=True)
        raise SystemExit(
            f"Checksum mismatch for {model['name']}:\n  expected {model['sha256']}\n  got      {actual}"
        )
    tmp.replace(target)
    print(f"[ok] {model['name']} verified ({model['license']})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and checksum-verify CrabBots ONNX models.")
    parser.add_argument(
        "--detection-only",
        action="store_true",
        help="Download only YuNet; useful for running the face-detection algorithm without SFace recognition.",
    )
    args = parser.parse_args()
    selected_models = MODELS[:1] if args.detection_only else MODELS
    for model in selected_models:
        try:
            download(model)
        except Exception as exc:  # noqa: BLE001
            print(f"[!!] failed to download {model['name']}: {exc}", file=sys.stderr)
            return 1
    print("\nModels ready in backend/models/")
    print("  YuNet  (detection)  - MIT")
    if not args.detection_only:
        print("  SFace  (embeddings) - Apache-2.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
