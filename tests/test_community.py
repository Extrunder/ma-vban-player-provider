"""Publication guards and the canonical community-provider layout."""

import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.configure_repository import configure
from scripts.package_community import package, validate
from vban.config import config_entries

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def release_tree(tmp_path):
    for name in ("LICENSE", "pyproject.toml", "README.md", "CHANGELOG.md", "uv.lock"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "vban", tmp_path / "vban", ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def test_canonical_folder_and_texts():
    manifest = json.loads((ROOT / "vban/manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "vban" and manifest["type"] == "player"
    assert manifest["requirements"] == []
    english = json.loads((ROOT / "vban/strings.json").read_text(encoding="utf-8"))
    russian = json.loads((ROOT / "vban/translations/ru.json").read_text(encoding="utf-8"))
    for entry in config_entries():
        assert english["config_entries"][entry.key]["label"]
        assert russian["config_entries"][entry.key]["label"]
    assert not (ROOT / "music_assistant/providers/vban").exists()


def test_publication_needs_actual_repository(release_tree, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    manifest_path = release_tree / "vban/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("documentation", None)
    manifest["codeowners"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate(release_tree) == "0.2.0"
    with pytest.raises(ValueError, match="configure_repository"):
        validate(release_tree, publication=True)
    configure(release_tree, "example-owner/ma-vban", "example-user")
    assert validate(release_tree, publication=True, version="0.2.0") == "0.2.0"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["codeowners"] == ["@example-user"]
    assert manifest["support_url"] == "https://github.com/example-owner/ma-vban/issues"


def test_release_guards_version_and_repository(release_tree, monkeypatch):
    configure(release_tree, "example-owner/ma-vban")
    with pytest.raises(ValueError, match="declares"):
        validate(release_tree, version="0.3.0")
    monkeypatch.setenv("GITHUB_REPOSITORY", "other-owner/other-repo")
    with pytest.raises(ValueError, match="workflow runs"):
        validate(release_tree, publication=True)


@pytest.mark.parametrize("repository", ["https://github.com/a/b", "a", "../repo", "a/b/c"])
def test_reject_invalid_repository(release_tree, repository):
    with pytest.raises(ValueError, match="owner/repository"):
        configure(release_tree, repository)


def test_package_has_one_provider_copy_and_no_cache(release_tree):
    for name in (".gitignore", ".dockerignore", "Dockerfile.community-test"):
        shutil.copyfile(ROOT / name, release_tree / name)
    path = package(release_tree, validate(release_tree))
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
    assert "vban/manifest.json" in names and "LICENSE" in names
    assert "vban/translations/ru.json" in names
    assert not any("__pycache__" in name or "site-packages" in name for name in names)
    assert "config.yaml" not in names and "Dockerfile" not in names
    assert path.with_suffix(".zip.sha256").is_file()
