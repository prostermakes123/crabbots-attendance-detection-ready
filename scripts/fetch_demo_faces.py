"""Fetch public-domain NASA portraits for demo data and test fixtures.

All images are official NASA photographs (public domain, 17 U.S.C. § 105),
retrieved through the NASA Image and Video Library API. They are used only as
clearly labelled demo data and automated-test fixtures. No endorsement is
implied and they do not represent CrabBots members.

Run:  python scripts/fetch_demo_faces.py
      python scripts/fetch_demo_faces.py --fixtures   (copy into tests/fixtures/faces)
"""

from __future__ import annotations

import argparse
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data" / "demo_faces"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "faces"

ASSET = "https://images-assets.nasa.gov/image/{nasa_id}/{nasa_id}~{size}.jpg"

# role: "member" -> demo gallery, "pair" -> second photo of an enrolled member
PEOPLE = [
    {"file": "Jack_Hathaway.jpg", "name": "Jack Hathaway", "nasa_id": "jsc2025e068207_alt", "role": "member"},
    {"file": "Jessica_Meir.jpg", "name": "Jessica Meir", "nasa_id": "NHQ202009150005", "role": "member"},
    {"file": "Sophie_Adenot.jpg", "name": "Sophie Adenot", "nasa_id": "jsc2025e058846_alt", "role": "member"},
    {"file": "Joshua_Kutryk.jpg", "name": "Joshua Kutryk", "nasa_id": "jsc2025e081360_alt", "role": "member"},
    {"file": "Soichi_Noguchi.jpg", "name": "Soichi Noguchi", "nasa_id": "jsc2016e096719", "role": "member"},
    {"file": "Terrence_Wilcutt.jpg", "name": "Terrence Wilcutt", "nasa_id": "jsc2003e41874", "role": "member"},
    {"file": "Mike_Anderson.jpg", "name": "Mike Anderson", "nasa_id": "jsc2010e013041", "role": "member"},
    {"file": "Mark_Lee.jpg", "name": "Mark Lee", "nasa_id": "S84-40242", "role": "member"},
    # Second, independent photos used to test "same person, different photo".
    {"file": "pairs/Jack_Hathaway_2.jpg", "name": "Jack Hathaway", "nasa_id": "jsc2024e013672", "role": "pair"},
    {"file": "pairs/Jessica_Meir_2.jpg", "name": "Jessica Meir", "nasa_id": "jsc2025e078605_alt", "role": "pair"},
]

ATTRIBUTION = """# Demo portrait attribution

All images in this folder are official NASA photographs retrieved through the
NASA Image and Video Library (images.nasa.gov) and are **public domain**
(17 U.S.C. § 105: works of the US federal government).

| File | Person | NASA ID |
| ---- | ------ | ------- |
{rows}

These images are demo/test data only. No endorsement by NASA or the depicted
individuals is implied, and they are not CrabBots member records.
"""


def fetch(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "CrabBots-Attendance/1.0 (demo data)"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if len(data) < 10_000:
        raise RuntimeError(f"suspiciously small download ({len(data)} bytes)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true", help="copy into tests/fixtures/faces")
    args = parser.parse_args()

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for person in PEOPLE:
        target = DEMO_DIR / person["file"]
        if target.is_file() and target.stat().st_size > 10_000:
            print(f"[ok] {person['file']}")
        else:
            print(f"[..] {person['name']} ({person['nasa_id']})")
            url = ASSET.format(nasa_id=person["nasa_id"], size="large")
            try:
                fetch(url, target)
            except Exception:
                try:
                    fetch(ASSET.format(nasa_id=person["nasa_id"], size="medium"), target)
                except Exception as exc:  # noqa: BLE001
                    print(f"[!!] {person['name']}: {exc}")
                    continue
        rows.append(f"| {person['file']} | {person['name']} | {person['nasa_id']} |")

    (DEMO_DIR / "ATTRIBUTION.md").write_text(ATTRIBUTION.format(rows="\n".join(rows)), encoding="utf-8")
    print(f"\nDemo faces in {DEMO_DIR}")

    if args.fixtures:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        for person in PEOPLE:
            source = DEMO_DIR / person["file"]
            if source.is_file():
                target = FIXTURE_DIR / Path(person["file"]).name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        (FIXTURE_DIR / "ATTRIBUTION.md").write_text(
            ATTRIBUTION.format(rows="\n".join(rows)) + "\nThese copies are test fixtures only.\n",
            encoding="utf-8",
        )
        print(f"Fixtures copied to {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
