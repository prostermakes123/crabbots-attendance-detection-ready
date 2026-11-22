"""Launch the app: `python -m backend.run`."""

from __future__ import annotations

import uvicorn

from .app.core.config import CONFIG
from .app.core.logging import configure_logging


def main() -> None:
    configure_logging(CONFIG.log_level)
    print(f"\n  CrabBots Attendance  ->  http://{CONFIG.host}:{CONFIG.port}\n")
    uvicorn.run(
        "backend.app.main:app",
        host=CONFIG.host,
        port=CONFIG.port,
        reload=False,
        log_level=CONFIG.log_level.lower(),
    )


if __name__ == "__main__":
    main()
