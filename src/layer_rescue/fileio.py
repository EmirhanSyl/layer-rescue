"""Atomic in-place rewriting of the G-code file Bambu Studio hands to the post-processor."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Callable, TypeVar

from .gcode import ResumeError
from .resume import ResumeOptions, ResumeReport, build_resume_gcode

R = TypeVar("R")


def _available_backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".layer-rescue.bak")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".layer-rescue.{counter}.bak")
        counter += 1
    return candidate



def rewrite_with(
    path: str | os.PathLike[str],
    builder: Callable[[str], tuple[str, R]],
    *,
    create_backup: bool = True,
) -> tuple[R, Path | None]:
    """Run ``builder`` on the file's text and replace the file atomically, keeping a backup."""
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise ResumeError(f"G-code file does not exist: {source_path}")
    if source_path.suffix.lower() not in {".gcode", ".gco"}:
        raise ResumeError("Post-processing MVP accepts raw .gcode files only.")

    text = source_path.read_text(encoding="utf-8", errors="replace")
    output, report = builder(text)
    backup_path: Path | None = None
    if create_backup:
        backup_path = _available_backup_path(source_path)
        shutil.copy2(source_path, backup_path)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=source_path.parent,
            prefix=source_path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, source_path)
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()
    return report, backup_path


def rewrite_gcode_file(
    path: str | os.PathLike[str],
    options: ResumeOptions,
    *,
    create_backup: bool = True,
) -> ResumeReport:
    report, backup_path = rewrite_with(path, lambda text: build_resume_gcode(text, options), create_backup=create_backup)
    return replace(report, backup_path=backup_path)
