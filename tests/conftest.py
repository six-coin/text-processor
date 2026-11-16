"""测试公共准备。

在导入 ``app`` 之前把三类目录指到临时位置——``app.paths`` 在导入时就会算出
DATA_DIR，晚一步就改不动了。
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

_BASE = Path(tempfile.gettempdir()) / "text-processor-tests" / uuid.uuid4().hex[:8]
os.environ["SIXCOIN_DATA_DIR"] = str(_BASE / "data")
os.environ["SIXCOIN_LOCAL_DIR"] = str(_BASE / "local")
os.environ["SIXCOIN_TEMP_DIR"] = str(_BASE / "temp")

import pytest  # noqa: E402

from app import paths  # noqa: E402


@pytest.fixture(autouse=True)
def clean_dirs():
    """每个用例都从空的 projects / processors 开始。"""
    for folder in (paths.PROJECTS_DIR, paths.PROCESSORS_DIR, paths.RECYCLE_DIR):
        shutil.rmtree(folder, ignore_errors=True)
    paths.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    paths.PROCESSORS_DIR.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture()
def project_root() -> Path:
    return paths.PROGRAM_DIR


@pytest.fixture()
def web_root() -> Path:
    return paths.WEB_DIR
