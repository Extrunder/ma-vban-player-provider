"""Set the real public GitHub repository and maintainer before releasing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def configure(root: Path, repository: str, maintainer: str | None = None) -> None:
    """Write repository-specific manifest links, without publishing anything."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository must be a GitHub owner/repository, without a URL")
    owner = (maintainer or repository.split("/", 1)[0]).removeprefix("@")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner):
        raise ValueError("Maintainer must be a GitHub user handle")
    path = root / "vban" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["codeowners"] = [f"@{owner}"]
    manifest["documentation"] = f"https://github.com/{repository}#readme"
    manifest["support_url"] = f"https://github.com/{repository}/issues"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="Public GitHub owner/repository")
    parser.add_argument("--maintainer", help="GitHub user handle; defaults to the repository owner")
    args = parser.parse_args()
    try:
        configure(Path(__file__).resolve().parents[1], args.repository, args.maintainer)
    except ValueError as err:
        parser.error(str(err))
    print(f"Configured public repository: https://github.com/{args.repository}")


if __name__ == "__main__":
    main()
