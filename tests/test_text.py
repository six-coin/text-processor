"""行切分与差异片段。"""

from __future__ import annotations

from app.core import diff
from app.core import text as text_tools


def test_stats_of_empty_text():
    assert text_tools.stats("") == {"chars": 0, "lines": 0}


def test_stats_counts_crlf():
    assert text_tools.stats("a\r\nb\r\n") == {"chars": 6, "lines": 2}


def test_split_remembers_trailing_newline():
    lines, trailing = text_tools.split("a\nb\n")
    assert lines == ["a", "b"]
    assert trailing is True


def test_split_without_trailing_newline():
    lines, trailing = text_tools.split("a\nb")
    assert trailing is False


def test_join_roundtrip():
    lines, trailing = text_tools.split("a\nb\n")
    assert text_tools.join(lines, trailing) == "a\nb\n"


def test_segments_marks_only_changes():
    left, right = diff.segments("abc", "axc")
    assert "".join(item[0] for item in left) == "abc"
    assert "".join(item[0] for item in right) == "axc"
    assert any(item[1] for item in left)
    assert any(item[1] for item in right)


def test_changed_lines_pairs_by_index():
    items, omitted = diff.changed_lines(["a", "b", "c"], ["a", "B", "c"])
    assert omitted == 0
    assert len(items) == 1
    assert items[0]["index"] == 1
    assert items[0]["before"] == "b"
    assert items[0]["after"] == "B"


def test_changed_lines_respects_limit():
    old = [str(index) for index in range(10)]
    new = [str(index) + "x" for index in range(10)]
    items, omitted = diff.changed_lines(old, new, limit=4)
    assert len(items) == 4
    assert omitted == 6


def test_decode_utf8():
    assert text_tools.decode_bytes("中文".encode()) == "中文"


def test_decode_gbk():
    assert text_tools.decode_bytes("中文".encode("gb18030")) == "中文"


def test_decode_utf16_with_bom():
    assert text_tools.decode_bytes("中文".encode("utf-16")) == "中文"


def test_decode_never_raises():
    assert isinstance(text_tools.decode_bytes(b"\xff\x00\xfe"), str)
