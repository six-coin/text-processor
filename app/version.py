"""版本号：全项目只有 ``pyproject.toml`` 一处。"""

from __future__ import annotations

import tomllib
from functools import lru_cache

from app import paths


@lru_cache(maxsize=1)
def version() -> str:
    """当前程序版本，来自 ``pyproject.toml`` 的 ``project.version``。"""
    try:
        with (paths.PROGRAM_DIR / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
        return str(data["project"]["version"])
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        return "0.0.0"
