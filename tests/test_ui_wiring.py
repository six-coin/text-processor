"""界面接线：JS 里引用的 id 与样式表必须真实存在。

这类错误在浏览器里只表现为「某个按钮点了没反应」，很难靠肉眼发现。
"""

from __future__ import annotations

import re

from app import paths

INDEX = paths.WEB_DIR / "index.html"
JS_DIR = paths.WEB_DIR / "js"
CSS_DIR = paths.WEB_DIR / "css"

ID_REF = re.compile(r'\$\$?\("#([A-Za-z0-9_-]+)"')
ID_DEF = re.compile(r'id="([A-Za-z0-9_-]+)"')
LINK = re.compile(r'href="([^"]+\.css)"')
SCRIPT = re.compile(r'src="([^"]+\.js)"')

#: 由 JS 在渲染时拼进 innerHTML 的元素，index.html 里查不到是正常的。
DYNAMIC_IDS = {"doc-version"}


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_every_referenced_id_exists():
    html = _html()
    defined = set(ID_DEF.findall(html))
    missing = []
    for path in JS_DIR.glob("*.js"):
        for name in ID_REF.findall(path.read_text(encoding="utf-8")):
            if name not in defined and name not in DYNAMIC_IDS:
                missing.append(f"{path.name}: {name}")
    assert missing == [], f"JS 引用了不存在的 id：{missing}"


def test_stylesheets_exist():
    for href in LINK.findall(_html()):
        assert (paths.WEB_DIR / href).is_file(), f"缺少样式表 {href}"


def test_scripts_exist_and_are_ordered():
    names = SCRIPT.findall(_html())
    assert names, "没有引用任何脚本"
    for src in names:
        assert (paths.WEB_DIR / src).is_file(), f"缺少脚本 {src}"
    # core 必须最先加载，main 必须最后
    assert names[0].endswith("core.js")
    assert names[-1].endswith("main.js")


def test_no_inline_handlers():
    html = _html()
    assert "onclick=" not in html
    assert "onchange=" not in html


def test_css_has_no_unbalanced_braces():
    for path in CSS_DIR.glob("*.css"):
        text = path.read_text(encoding="utf-8")
        assert text.count("{") == text.count("}"), f"{path.name} 花括号不成对"


def test_js_has_no_debug_leftovers():
    for path in JS_DIR.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        assert "console.log(" not in text, f"{path.name} 残留 console.log"
        assert "debugger" not in text
