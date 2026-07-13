from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from .config import APP_DIR
from .skills import _read_manifest

MAX_FILES = 500
MAX_BYTES = 50 * 1024 * 1024


def import_local_skill(workspace: str | Path, source: str | Path) -> dict[str, Any]:
    """Copy a validated local skill into the workspace-managed skill library."""
    root = Path(workspace).resolve()
    candidate = Path(source).expanduser().resolve()
    manifest = candidate / "SKILL.md"
    if not candidate.is_dir() or not manifest.is_file():
        raise ValueError("local import must be a directory containing SKILL.md")

    files, content_hash = _validate_tree(candidate)
    source_manifest = _read_manifest(manifest)
    destination = root / APP_DIR / "skills" / source_manifest.name
    already_imported = destination.exists()
    if already_imported:
        _, existing_hash = _validate_tree(destination)
        if existing_hash != content_hash:
            raise ValueError(f"managed skill '{source_manifest.name}' already exists with different content")
    if not already_imported:
        for source_file in files:
            target = destination / source_file.relative_to(candidate)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)
    return {
        "id": f"local:{content_hash}",
        "name": source_manifest.name,
        "description": source_manifest.description,
        "content_hash": f"sha256:{content_hash}",
        "managed_path": str(destination),
        "already_imported": already_imported,
    }


def _validate_tree(root: Path) -> tuple[list[Path], str]:
    files: list[Path] = []
    total_bytes = 0
    digest = hashlib.sha256()
    for current, dirs, names in os.walk(root, followlinks=False):
        directory = Path(current)
        if directory.is_symlink():
            raise ValueError("local import cannot contain symbolic-link directories")
        for name in sorted(names):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("local import can only contain regular files")
            files.append(path)
            if len(files) > MAX_FILES:
                raise ValueError(f"local import exceeds {MAX_FILES} files")
            total_bytes += path.stat().st_size
            if total_bytes > MAX_BYTES:
                raise ValueError("local import exceeds 50 MiB")
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return files, digest.hexdigest()
