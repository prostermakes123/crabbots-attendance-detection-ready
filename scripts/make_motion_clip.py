"""Create a synthetic "person walks past the camera" clip from one portrait.

This is deliberately synthetic and documented as such: it exercises tracking,
temporal voting and attendance deduplication with controlled motion (translation,
scale, motion blur, exposure drift) without needing recorded footage of a real
person. It is *not* used to claim real-world accuracy.

Usage:
  python scripts/make_motion_clip.py --image tests/fixtures/faces/Jack_Hathaway.jpg \
      --out data/demo/walk_past.mp4 --seconds 6
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT, FPS = 960, 540, 24


def make_clip(image_path: Path, out_path: Path, seconds: float = 6.0) -> Path:
    portrait = cv2.imread(str(image_path))
    if portrait is None:
        raise SystemExit(f"Could not read {image_path}")
    h, w = portrait.shape[:2]
    # Head-and-shoulders crop around the upper-middle of a portrait.
    crop_h = int(h * 0.55)
    crop_w = int(crop_h * 0.80)
    cx, cy = w // 2, int(h * 0.32)
    x0, y0 = max(0, cx - crop_w // 2), max(0, cy - crop_h // 2)
    cutout = portrait[y0 : y0 + crop_h, x0 : x0 + crop_w].copy()

    # Soft oval alpha mask so the cutout does not look like a pasted rectangle.
    mask = np.zeros((crop_h, crop_w), dtype=np.float32)
    cv2.ellipse(mask, (crop_w // 2, crop_h // 2), (crop_w // 2, crop_h // 2), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=crop_w * 0.04)
    mask = np.clip(mask, 0, 1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise SystemExit("Could not open video writer (codec unavailable).")

    frames = int(seconds * FPS)
    base_scale = HEIGHT * 0.72 / crop_h
    for i in range(frames):
        t = i / max(1, frames - 1)
        # Left -> right sweep with a gentle approach/retreat.
        px = -0.15 + 1.30 * t
        scale = base_scale * (1.0 + 0.28 * np.sin(np.pi * t))
        new_w, new_h = int(crop_w * scale), int(crop_h * scale)
        person = cv2.resize(cutout, (new_w, new_h), interpolation=cv2.INTER_AREA)
        alpha = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Studio-ish background with a vertical gradient and soft vignette.
        grad = np.linspace(38, 22, HEIGHT, dtype=np.float32)[:, None, None]
        background = np.repeat(np.repeat(grad, WIDTH, axis=1), 3, axis=2)
        background = background + np.array([12, 16, 22], dtype=np.float32)
        vignette = np.clip(1.15 - np.linalg.norm(
            np.stack(np.meshgrid(np.linspace(-1, 1, WIDTH), np.linspace(-1, 1, HEIGHT))), axis=0), 0.55, 1.15
        )
        background = np.clip(background * vignette[..., None], 0, 255).astype(np.uint8)

        x = int(px * WIDTH)
        y = int((HEIGHT - new_h) / 2 + 0.05 * HEIGHT * np.cos(np.pi * t))
        x0d, y0d = max(0, x), max(0, y)
        x1d, y1d = min(WIDTH, x + new_w), min(HEIGHT, y + new_h)
        if x1d > x0d and y1d > y0d:
            sx0, sy0 = x0d - x, y0d - y
            sx1, sy1 = sx0 + (x1d - x0d), sy0 + (y1d - y0d)
            roi = background[y0d:y1d, x0d:x1d].astype(np.float32)
            src = person[sy0:sy1, sx0:sx1].astype(np.float32)
            a = alpha[sy0:sy1, sx0:sx1][..., None]
            background[y0d:y1d, x0d:x1d] = np.clip(src * a + roi * (1 - a), 0, 255).astype(np.uint8)

        # Speed-dependent motion blur + slight exposure drift.
        speed = abs(np.cos(np.pi * t)) * 9 + 2
        kernel = np.zeros((1, int(speed), 1), dtype=np.float32)
        kernel[0, :, 0] = 1.0 / kernel.shape[1]
        frame = cv2.filter2D(background, -1, kernel)
        frame = np.clip(frame.astype(np.float32) * (0.95 + 0.08 * np.sin(3 * np.pi * t)), 0, 255).astype(np.uint8)
        writer.write(frame)

    writer.release()
    print(f"wrote {out_path} ({frames} frames, {WIDTH}x{HEIGHT} @ {FPS} fps)")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", default="data/demo/walk_past.mp4")
    parser.add_argument("--seconds", type=float, default=6.0)
    args = parser.parse_args()
    make_clip(Path(args.image), Path(args.out), args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
