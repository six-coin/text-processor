"""四类目录的解析规则。"""

from __future__ import annotations

from pathlib import Path

from app import paths


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("SIXCOIN_DATA_DIR", str(tmp_path / "custom"))
    assert paths.read_data_dir() == tmp_path / "custom"


def test_normalize_appends_project_name():
    assert paths.normalize_data_dir("D:/data").name == paths.PROJECT
    assert paths.normalize_data_dir("D:/data/text-processor").name == paths.PROJECT
    assert paths.normalize_data_dir("D:/data/TEXT-PROCESSOR").name == "TEXT-PROCESSOR"


def test_normalize_strips_quotes_and_expands_user():
    assert paths.normalize_data_dir('  "D:/data"  ') == paths.normalize_data_dir("D:/data")
    assert paths.normalize_data_dir("").name == paths.PROJECT


def test_normalize_relative_uses_base():
    base = Path("C:/base")
    assert paths.normalize_data_dir("sub", base) == base / "sub" / paths.PROJECT


def test_resolve_user_path_relative_to_data_dir():
    assert paths.resolve_user_path("notes") == paths.DATA_DIR / "notes"
    absolute = paths.resolve_user_path("D:/x")
    assert absolute == Path("D:/x")


def test_data_dir_is_absolute():
    assert paths.DATA_DIR.is_absolute()
    assert paths.LOG_DIR.parent == paths.LOCAL_DIR
    assert paths.TEMP_DIR != paths.DATA_DIR


def test_pointer_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("SIXCOIN_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "DATA_POINTER", tmp_path / "data-dir.txt")
    target = tmp_path / "elsewhere" / paths.PROJECT
    paths.write_data_dir(target)
    assert paths.read_data_dir() == target


def test_pending_marks_and_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA_PENDING", tmp_path / "pending.txt")
    monkeypatch.setattr(paths, "DATA_POINTER", tmp_path / "data-dir.txt")
    monkeypatch.setattr(paths, "LOCAL_DIR", tmp_path)
    target = paths.request_data_dir(str(tmp_path / "new"))
    assert paths.pending_data_dir() == target
    paths.clear_pending_data_dir()
    assert paths.pending_data_dir() is None
