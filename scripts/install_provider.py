"""Copy the provider into a stopped Music Assistant installation or source tree."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers-dir",
        required=True,
        type=Path,
        help="Existing music_assistant/providers directory (MA 2.10.13)",
    )
    args = parser.parse_args()
    providers = args.providers_dir.resolve()
    if not providers.is_dir() or providers.name != "providers":
        parser.error(
            "--providers-dir must point to an existing music_assistant/providers directory"
        )
    if not (providers.parent / "mass.py").is_file():
        parser.error("Target is not a Music Assistant source/package directory (mass.py missing)")
    source = Path(__file__).resolve().parents[1] / "vban"
    target = providers / "vban"
    if target.exists():
        parser.error(f"{target} already exists; preserve/remove the old copy before reinstalling")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"Installed VBAN provider: {target}")
    print("Restart Music Assistant, then add the VBAN Player provider in Settings.")


if __name__ == "__main__":
    main()
