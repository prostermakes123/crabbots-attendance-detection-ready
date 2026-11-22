"""Download a reproducible LFW subset for threshold calibration and evaluation.

LFW is used here as an *evaluation* dataset only (research use), never as
enrolment data and never committed to the repository. The script pulls a slice
of the Hugging Face mirror ``logasja/lfw`` through the datasets-server API and
caches images under ``data/eval/lfw``.

Run:  python scripts/fetch_lfw_subset.py --rows 1200
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "eval" / "lfw"
MANIFEST = CACHE / "manifest.json"
API = "https://datasets-server.huggingface.co/rows"
UA = {"User-Agent": "CrabBots-Attendance/1.0 (evaluation)"}


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_page(offset: int, length: int = 100) -> list[dict]:
    params = urllib.parse.urlencode(
        {"dataset": "logasja/lfw", "config": "default", "split": "train", "offset": offset, "length": length}
    )
    data = fetch_json(f"{API}?{params}")
    return data.get("rows", [])


def download(url: str, target: Path) -> bool:
    if target.is_file() and target.stat().st_size > 1000:
        return True
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
            if len(payload) < 500:
                return False
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            return True
        except Exception:  # noqa: BLE001
            if attempt == 2:
                return False
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1200, help="number of images to cache")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for offset in range(0, args.rows, 100):
        page = fetch_page(offset, 100)
        if not page:
            break
        for item in page:
            label = item["row"]["label"]
            image = item["row"]["image"]
            entries.append(
                {
                    "idx": item["row_idx"],
                    "label": label,
                    "src": image["src"],
                    "path": f"images/{label}/{item['row_idx']}.jpg",
                }
            )
        print(f"listed {len(entries)} rows")

    def work(entry: dict) -> bool:
        return download(entry["src"], CACHE / entry["path"])

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(work, entries))
    kept = [entry for entry, ok in zip(entries, results) if ok]
    for entry in kept:
        entry.pop("src", None)
    MANIFEST.write_text(json.dumps(kept, indent=1), encoding="utf-8")
    identities = len({entry["label"] for entry in kept})
    print(f"cached {len(kept)} images across {identities} identities -> {CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
