"""Validate and package the community provider; never publish or access the network."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def validate(root: Path, *, publication: bool = False, version: str | None = None) -> str:
    """Check the release version, provider layout, licence and publication metadata."""
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    release_version = project["version"]
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", release_version):
        raise ValueError("Community releases require a MAJOR.MINOR.PATCH version")
    if version is not None and version != release_version:
        raise ValueError(f"Requested {version} but pyproject.toml declares {release_version}")
    if project.get("license") != "Apache-2.0" or not (root / "LICENSE").is_file():
        raise ValueError("The Apache-2.0 licence and LICENSE file must be present")
    folder = root / "vban"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("domain") != folder.name or manifest.get("type") != "player":
        raise ValueError("Provider domain/folder must be vban and type must be player")
    if manifest.get("requirements") != []:
        raise ValueError("This provider is designed to have no external requirements")
    if not (folder / "__init__.py").is_file() or not (folder / "setup_flow.py").is_file():
        raise ValueError("Provider entry point and setup flow must be present")
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Community providers cannot contain symbolic links: {path}")
    if publication:
        documentation = manifest.get("documentation", "")
        match = re.fullmatch(r"https://github.com/([^/]+/[^/#]+)#readme", documentation)
        if match is None or not manifest.get("codeowners"):
            raise ValueError("Run scripts/configure_repository.py with your real GitHub repository")
        repository = match[1]
        if manifest.get("support_url") != f"https://github.com/{repository}/issues":
            raise ValueError("Support URL must point to the provider repository's issues")
        if expected := os.environ.get("GITHUB_REPOSITORY"):
            if repository.lower() != expected.lower():
                raise ValueError(f"Manifest points to {repository}, workflow runs in {expected}")
    return release_version


def package(root: Path, version: str) -> Path:
    """Package source, CI and tests, excluding caches and old image/App packaging."""
    destination = root / "dist" / f"vban-community-{version}.zip"
    destination.parent.mkdir(exist_ok=True)
    names = [
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
        "pyproject.toml",
        "uv.lock",
        ".gitignore",
        ".dockerignore",
        "Dockerfile.community-test",
    ]
    files = [root / name for name in names]
    for directory in ("vban", ".github", "scripts", "tests", "docs"):
        files.extend(
            path
            for path in (root / directory).rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and "__pycache__" not in path.parts
            and path.suffix in (".py", ".json", ".svg", ".yml", ".md", ".sh")
            and path.name != "package_app.py"
        )
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(root))
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(
        f"{digest}  {destination.name}\n", encoding="ascii"
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-publication", action="store_true")
    parser.add_argument("--version", help="Require this exact release version")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        version = validate(root, publication=args.check_publication, version=args.version)
        destination = package(root, version)
    except ValueError as err:
        parser.error(str(err))
    print(destination)


if __name__ == "__main__":
    main()
