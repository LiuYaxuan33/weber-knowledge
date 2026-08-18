"""Container entrypoint: restore the portable index, then launch Gradio."""

from __future__ import annotations

import os

from import_data import import_data
from store import collection_stats


def main() -> None:
    os.environ.setdefault("WEBER_NO_BROWSER", "1")
    os.environ.setdefault("HOST", "0.0.0.0")
    os.environ.setdefault("PORT", "7860")

    if collection_stats()["chunks"] == 0:
        archive = os.path.join(os.path.dirname(__file__), "data", "weber_data.npz")
        print("Vector index not found; restoring portable archive...", flush=True)
        import_data(archive)

    from app import main as run_app
    run_app()


if __name__ == "__main__":
    main()
