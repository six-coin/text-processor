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


# ---------- 只读文件 ----------


def test_move_item_clears_read_only_and_retries(tmp_path, monkeypatch):
    """只读文件不能把搬迁卡住：用户的数据目录里这类文件很常见。

    ``shutil.move`` 跨盘时是「复制 + 删源」，删只读文件会得到「拒绝访问」；
    这里模拟那一次失败，确认去掉只读位后会再搬一次。
    """
    import shutil
    import stat

    source = tmp_path / "a.bin"
    source.write_text("x", encoding="utf-8")
    source.chmod(stat.S_IREAD)
    target = tmp_path / "out" / "a.bin"
    target.parent.mkdir()

    calls = {"count": 0}
    real_move = shutil.move

    def flaky_move(src, dst):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError(13, "拒绝访问")
        return real_move(src, dst)

    monkeypatch.setattr(paths.shutil, "move", flaky_move)
    paths._move_item(source, target)

    assert calls["count"] == 2
    assert target.is_file()


def test_clear_read_only_reaches_nested_files(tmp_path):
    """目录里嵌着的只读文件也要清掉，否则删旧目录会停在那一层。"""
    import stat

    nested = tmp_path / "data" / "2026"
    nested.mkdir(parents=True)
    locked = nested / "a.bin"
    locked.write_text("x", encoding="utf-8")
    locked.chmod(stat.S_IREAD)

    paths._clear_read_only(tmp_path / "data")

    assert locked.stat().st_mode & stat.S_IWRITE


def test_move_item_clears_a_half_copied_destination(tmp_path, monkeypatch):
    """上一次复制到一半留下的残骸要先清掉，否则源目录会被塞进同名目录里。"""
    import shutil
    import stat

    source = tmp_path / "data"
    source.mkdir()
    (source / "a.bin").write_text("x", encoding="utf-8")
    (source / "a.bin").chmod(stat.S_IREAD)
    destination = tmp_path / "out" / "data"
    destination.mkdir(parents=True)
    (destination / "a.bin").write_text("partial", encoding="utf-8")

    calls = {"count": 0}
    real_move = shutil.move

    def flaky_move(src, dst):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError(13, "拒绝访问")
        return real_move(src, dst)

    monkeypatch.setattr(paths.shutil, "move", flaky_move)
    paths._move_item(source, destination)

    assert calls["count"] == 2
    # 内容落在 out/data/ 里，而不是 out/data/data/
    assert (destination / "a.bin").read_text(encoding="utf-8") == "x"
    assert not (destination / "data").exists()
