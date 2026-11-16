"""AI 提示词必须自包含：契约、三种类型、约束、示例、用户需求。"""

from __future__ import annotations

from app.core import prompt


def test_prompt_contains_request():
    text = prompt.build("把每一行倒过来")
    assert "把每一行倒过来" in text


def test_prompt_explains_contract():
    text = prompt.build("x")
    for token in ("init()", "process(", "line", "file", "check", "args", "default"):
        assert token in text


def test_prompt_forbids_side_effects():
    text = prompt.build("x")
    assert "不读写文件" in text
    assert "subprocess" in text


def test_prompt_has_examples():
    text = prompt.build("x")
    assert text.count("```python") >= 3


def test_empty_request_still_produces_prompt():
    text = prompt.build("   ")
    assert "init()" in text
    assert len(text) > 1000
