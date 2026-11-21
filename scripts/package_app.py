"""Build an installable local Home Assistant App/source bundle."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / "dist" / "music_assistant_vban-0.1.0.zip"
    destination.parent.mkdir(exist_ok=True)
    files = [
        root / name
        for name in (
            "config.yaml",
            "Dockerfile",
            ".dockerignore",
            "compose.yaml",
            "README.md",
            "pyproject.toml",
            "uv.lock",
        )
    ]
    files.extend((root / "vban").rglob("*.py"))
    files.extend((root / "vban").rglob("*.json"))
    files.extend((root / "scripts").glob("*.py"))
    files.extend((root / "tests").glob("*.py"))
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, Path("music_assistant_vban") / path.relative_to(root))
    print(destination)


if __name__ == "__main__":
    main()
