"""Repeatable recognition evaluation: detection, verification, identification, latency.

Protocol (documented honestly in docs/RESEARCH.md):
  * Data: LFW subset (logasja/lfw mirror), evaluation only.
  * Verification pairs are sampled from cached identities: disjoint images for
    same-identity pairs, random cross-identity pairs for negatives.
  * Identification: one enrolment image per identity; a *different* image of
    the same person is the query. Identities not enrolled act as unknown
    probes, which is how false accepts are measured.
  * Detection rate = share of images with exactly one detected face at the
    configured processing width.

Usage:
  python scripts/fetch_lfw_subset.py --rows 1200
  python scripts/evaluate.py [--pairs 400]
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import CONFIG  # noqa: E402
from backend.app.db.database import DEFAULT_SETTINGS  # noqa: E402
from backend.app.services.detector import FaceDetector  # noqa: E402
from backend.app.services.recognizer import FaceRecognizer  # noqa: E402

CACHE = ROOT / "data" / "eval" / "lfw"
OUT_DIR = ROOT / "evaluation" / "results"


def l2(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 1e-9 else vec


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def roc_curve(pos: list[float], neg: list[float], steps: int = 400):
    thresholds = np.linspace(0.0, 1.0, steps)
    tpr, fpr = [], []
    pos_arr, neg_arr = np.array(pos), np.array(neg)
    for t in thresholds:
        tpr.append(float((pos_arr >= t).mean()) if pos_arr.size else 0.0)
        fpr.append(float((neg_arr >= t).mean()) if neg_arr.size else 0.0)
    return thresholds, np.array(tpr), np.array(fpr)


def eer(tpr: np.ndarray, fpr: np.ndarray) -> float:
    idx = int(np.argmin(np.abs(tpr - (1 - fpr))))
    return float((tpr[idx] + (1 - fpr[idx])) / 2)


def tar_at_far(tpr: np.ndarray, fpr: np.ndarray, target: float) -> float:
    mask = fpr <= target
    return float(tpr[mask].max()) if mask.any() else 0.0


def auc(tpr: np.ndarray, fpr: np.ndarray) -> float:
    order = np.argsort(fpr)
    return float(np.trapezoid(tpr[order], fpr[order]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=400)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    manifest_path = CACHE / "manifest.json"
    if not manifest_path.is_file():
        print("No LFW cache found. Run: python scripts/fetch_lfw_subset.py", file=sys.stderr)
        return 1
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_identity: dict[str, list[dict]] = {}
    for entry in entries:
        by_identity.setdefault(str(entry["label"]), []).append(entry)
    identities = sorted(by_identity)
    multi = [i for i in identities if len(by_identity[i]) >= 2]
    print(f"loaded {len(entries)} images, {len(identities)} identities ({len(multi)} with 2+ photos)")

    detector = FaceDetector(CONFIG.yunet_path, 0.7)
    recognizer = FaceRecognizer(CONFIG.sface_path)
    processing_width = int(DEFAULT_SETTINGS["processing_width"])

    embeddings: dict[int, np.ndarray] = {}
    detection_ok = 0
    detection_multi = 0
    detection_miss = 0
    latencies: list[float] = []
    started = time.perf_counter()

    for index, entry in enumerate(entries):
        path = CACHE / entry["path"]
        image = cv2.imread(str(path))
        if image is None:
            detection_miss += 1
            continue
        h, w = image.shape[:2]
        scale = min(1.0, processing_width / w)
        work = cv2.resize(image, (int(w * scale), int(h * scale))) if scale < 0.999 else image
        t0 = time.perf_counter()
        faces = detector.detect(work, 0.7)
        if len(faces) == 0:
            detection_miss += 1
            continue
        if len(faces) > 1:
            detection_multi += 1
            faces = [max(faces, key=lambda f: f.bbox[2] * f.bbox[3])]
        face = faces[0].scaled(1.0 / scale) if scale < 0.999 else faces[0]
        vector = recognizer.embed(image, face)
        latencies.append((time.perf_counter() - t0) * 1000)
        embeddings[entry["idx"]] = l2(vector)
        detection_ok += 1
        if (index + 1) % 200 == 0:
            print(f"  embedded {index + 1}/{len(entries)}")

    total = len(entries)
    detection_rate = detection_ok / total if total else 0.0
    print(f"detection: {detection_ok}/{total} ({detection_rate * 100:.1f}%), multi-face {detection_multi}")

    # ---- verification -----------------------------------------------------
    rng = random.Random(args.seed)
    usable_multi = [i for i in multi if sum(1 for e in by_identity[i] if e["idx"] in embeddings) >= 2]
    rng.shuffle(usable_multi)
    positive_pairs = []
    for identity in usable_multi:
        if len(positive_pairs) >= args.pairs:
            break
        photos = [e for e in by_identity[identity] if e["idx"] in embeddings]
        if len(photos) < 2:
            continue
        a, b = rng.sample(photos, 2)
        positive_pairs.append((a["idx"], b["idx"]))

    all_idx = list(embeddings)
    negative_pairs = []
    label_of = {e["idx"]: str(e["label"]) for e in entries}
    while len(negative_pairs) < args.pairs and len(all_idx) > 2:
        a, b = rng.sample(all_idx, 2)
        if label_of[a] != label_of[b]:
            negative_pairs.append((a, b))

    pos_scores = [cosine(embeddings[a], embeddings[b]) for a, b in positive_pairs]
    neg_scores = [cosine(embeddings[a], embeddings[b]) for a, b in negative_pairs]
    thresholds, tpr, fpr = roc_curve(pos_scores, neg_scores)
    best = int(np.argmax(tpr - fpr))
    best_threshold = float(thresholds[best])
    best_accuracy = float(((np.array(pos_scores) >= best_threshold).mean()
                           + (np.array(neg_scores) < best_threshold).mean()) / 2)

    operating = float(DEFAULT_SETTINGS["recognition_threshold"])
    tar = float((np.array(pos_scores) >= operating).mean()) if pos_scores else 0.0
    far = float((np.array(neg_scores) >= operating).mean()) if neg_scores else 0.0

    verification = {
        "positive_pairs": len(pos_scores),
        "negative_pairs": len(neg_scores),
        "positive_similarity_mean": round(statistics.fmean(pos_scores), 4) if pos_scores else None,
        "negative_similarity_mean": round(statistics.fmean(neg_scores), 4) if neg_scores else None,
        "positive_similarity_p5": round(float(np.percentile(pos_scores, 5)), 4) if pos_scores else None,
        "negative_similarity_p95": round(float(np.percentile(neg_scores, 95)), 4) if neg_scores else None,
        "auc": round(auc(tpr, fpr), 4),
        "eer": round(eer(tpr, fpr), 4),
        "tar_at_far_1pct": round(tar_at_far(tpr, fpr, 0.01), 4),
        "best_threshold": round(best_threshold, 4),
        "best_accuracy": round(best_accuracy, 4),
        "operating_threshold": operating,
        "tar_at_operating": round(tar, 4),
        "far_at_operating": round(far, 4),
    }

    # ---- identification (1:N) --------------------------------------------
    enrolled_identities = usable_multi[:150]
    enrolled_vectors = []
    enrolled_labels = []
    for identity in enrolled_identities:
        photos = [e for e in by_identity[identity] if e["idx"] in embeddings]
        enrolled_vectors.append(embeddings[photos[0]["idx"]])
        enrolled_labels.append(identity)
    matrix = np.vstack(enrolled_vectors) if enrolled_vectors else np.zeros((0, 128))
    enrolled_set = set(enrolled_labels)

    rank1 = 0
    known_queries = 0
    false_accepts = 0
    unknown_queries = 0
    rejection_threshold = operating
    margin = float(DEFAULT_SETTINGS["recognition_margin"])

    for identity in usable_multi:
        photos = [e for e in by_identity[identity] if e["idx"] in embeddings]
        if len(photos) < 2:
            continue
        query = embeddings[photos[-1]["idx"]]
        scores = matrix @ query
        order = np.argsort(scores)[::-1]
        top, second = scores[order[0]], scores[order[1]] if len(order) > 1 else -1
        if identity in enrolled_set:
            known_queries += 1
            if enrolled_labels[order[0]] == identity and top >= rejection_threshold and (top - second) >= margin:
                rank1 += 1
        else:
            unknown_queries += 1
            if top >= rejection_threshold and (top - second) >= margin:
                false_accepts += 1

    identification = {
        "enrolled_identities": len(enrolled_labels),
        "known_queries": known_queries,
        "rank1_accuracy": round(rank1 / known_queries, 4) if known_queries else None,
        "unknown_queries": unknown_queries,
        "unknown_false_accept_rate": round(false_accepts / unknown_queries, 4) if unknown_queries else None,
        "threshold": rejection_threshold,
        "margin": margin,
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "name": "LFW subset (logasja/lfw mirror)",
            "images": total,
            "identities": len(identities),
            "note": "Evaluation-only; not committed to the repository; not used for enrolment.",
        },
        "models": {
            "detector": "OpenCV YuNet 2023mar (MIT)",
            "recognizer": "OpenCV SFace 2021dec (Apache-2.0, 128-D)",
            "processing_width": processing_width,
        },
        "detection": {
            "images": total,
            "detected": detection_ok,
            "missed": detection_miss,
            "multiple_faces": detection_multi,
            "detection_rate": round(detection_rate, 4),
        },
        "verification": verification,
        "identification": identification,
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 1) if latencies else None,
            "p50": round(float(np.percentile(latencies, 50)), 1) if latencies else None,
            "p95": round(float(np.percentile(latencies, 95)), 1) if latencies else None,
            "note": "detect + align + embed per image at processing width; excludes JPEG decode",
        },
        "wall_time_seconds": round(time.perf_counter() - started, 1),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = f"""# Recognition evaluation

Generated {report['generated_at']} from {total} LFW images ({len(identities)} identities).
Evaluation data only - not committed, not used for enrolment.

| Metric | Value |
| --- | --- |
| Detection rate | {report['detection']['detection_rate'] * 100:.1f}% |
| Verification AUC | {verification['auc']:.3f} |
| Equal error rate | {verification['eer'] * 100:.1f}% |
| TAR @ FAR 1% | {verification['tar_at_far_1pct'] * 100:.1f}% |
| TAR @ operating threshold {operating:.2f} | {verification['tar_at_operating'] * 100:.1f}% |
| FAR @ operating threshold {operating:.2f} | {verification['far_at_operating'] * 100:.1f}% |
| 1:N rank-1 (gallery {identification['enrolled_identities']}) | {(identification['rank1_accuracy'] or 0) * 100:.1f}% |
| Unknown false-accept rate | {(identification['unknown_false_accept_rate'] or 0) * 100:.1f}% |
| Latency p50 / p95 | {report['latency_ms']['p50']} / {report['latency_ms']['p95']} ms |
"""
    (OUT_DIR / "report.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
