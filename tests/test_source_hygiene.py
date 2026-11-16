"""源码卫生：依赖、版本、忽略项。"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_declares_runtime_deps():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = " ".join(data["project"]["dependencies"])
    assert "pywebview" in deps
    assert "loguru" in deps
    assert data["project"]["requires-python"].startswith(">=3.11")


def test_lock_file_covers_dependencies():
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "text-processor"' in lock
    for package in ("pywebview", "loguru"):
        assert f'name = "{package}"' in lock


def test_no_requirements_txt():
    assert not (ROOT / "requirements.txt").exists()


def test_python_version_file():
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip().startswith("3.11")


def test_gitignore_covers_venv_and_caches():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for token in (".venv/", "__pycache__/", ".ruff_cache/", ".pytest_cache/"):
        assert token in text


def test_entry_is_thin():
    source = (ROOT / "main.pyw").read_text(encoding="utf-8")
    assert "from app.ui.app import main" in source
    assert len(source.splitlines()) < 15


def test_app_does_not_import_webview_in_core():
    for path in (ROOT / "app" / "core").glob("*.py"):
        assert "import webview" not in path.read_text(encoding="utf-8")


def test_ruff_config_excludes_legacy():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "old" in data["tool"]["ruff"]["exclude"]
