"""文档一致性：README 只是岔路口，两份手册同节同序。"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ZH = DOCS / "readme" / "zh-CN.md"
EN = DOCS / "readme" / "en-US.md"

HEADING = re.compile(r"^## (.+)$", re.MULTILINE)


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _head(path: Path, count: int) -> list[str]:
    """标题之后的第 1、2、3 个非空行。"""
    body = [line for line in _lines(path)[1:] if line.strip()]
    return body[:count]


def test_readme_is_only_a_language_index():
    lines = [line for line in _lines(ROOT / "README.md") if line.strip()]
    assert lines[0] == "# text-processor"
    assert lines[1] == "- [简体中文](docs/readme/zh-CN.md)"
    assert lines[2] == "- [English](docs/readme/en-US.md)"
    assert len(lines) == 3


def test_readme_links_resolve():
    for target in ("docs/readme/zh-CN.md", "docs/readme/en-US.md"):
        assert (ROOT / target).is_file()


def test_docs_files_exist():
    for name in ("architecture.md", "configuration.md", "extending.md"):
        assert (DOCS / name).is_file(), f"缺少 docs/{name}"


def test_manuals_start_with_title_intro_and_link():
    assert _lines(ZH)[0].startswith("# ") and _lines(ZH)[0].endswith(" 使用手册")
    assert _lines(EN)[0].startswith("# ") and _lines(EN)[0].endswith(" User Manual")
    for path in (ZH, EN):
        intro, link = _head(path, 2)
        assert "[" not in intro and "`" not in intro and "*" not in intro
    assert _head(ZH, 2)[1] == "[English](en-US.md)"
    assert _head(EN, 2)[1] == "[简体中文](zh-CN.md)"


def test_english_intro_matches_pyproject_description():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert _head(EN, 1)[0] == data["project"]["description"]


def test_manuals_have_the_same_sections():
    zh = HEADING.findall(ZH.read_text(encoding="utf-8"))
    en = HEADING.findall(EN.read_text(encoding="utf-8"))
    assert len(zh) == len(en), f"章节数不同：{len(zh)} vs {len(en)}"
    for left, right in zip(zh, en, strict=True):
        assert left.split(" ")[0] == right.split(" ")[0], f"章节编号不同：{left} / {right}"


def test_manuals_are_not_stubs():
    assert len(ZH.read_text(encoding="utf-8")) > 3000
    assert len(EN.read_text(encoding="utf-8")) > 3000


def test_manual_cross_links_exist():
    for path in (ZH, EN):
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\((\.\./[^)]+)\)", text):
            assert (path.parent / target).resolve().is_file(), f"{path.name} 里的 {target} 打不开"
