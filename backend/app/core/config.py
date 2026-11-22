"""Application configuration.

Configuration is intentionally small and explicit: a few environment variables
for deployment concerns, everything else lives in the database so it can be
changed at runtime from the Settings page.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (avoids a dependency just for local demos)."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(REPO_ROOT / ".env")


def _resolve(value: str, default: str) -> Path:
    path = Path(value or default)
    return path if path.is_absolute() else (REPO_ROOT / path)


@dataclass(frozen=True)
class AppConfig:
    repo_root: Path
    db_path: Path
    model_dir: Path
    data_dir: Path
    admin_token: str
    host: str
    port: int
    log_level: str

    @property
    def yunet_path(self) -> Path:
        return self.model_dir / "face_detection_yunet_2023mar.onnx"

    @property
    def sface_path(self) -> Path:
        return self.model_dir / "face_recognition_sface_2021dec.onnx"

    @property
    def static_dir(self) -> Path:
        return REPO_ROOT / "backend" / "app" / "static"


def load_config() -> AppConfig:
    db_path = _resolve(os.getenv("CRABBOTS_DB_PATH", ""), "data/crabbots.db")
    model_dir = _resolve(os.getenv("CRABBOTS_MODEL_DIR", ""), "backend/models")
    return AppConfig(
        repo_root=REPO_ROOT,
        db_path=db_path,
        model_dir=model_dir,
        data_dir=db_path.parent,
        admin_token=os.getenv("CRABBOTS_ADMIN_TOKEN", "").strip(),
        host=os.getenv("CRABBOTS_HOST", "127.0.0.1"),
        port=int(os.getenv("CRABBOTS_PORT", "8000")),
        log_level=os.getenv("CRABBOTS_LOG_LEVEL", "INFO").upper(),
    )


CONFIG = load_config()
