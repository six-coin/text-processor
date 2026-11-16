"""文案层：键覆盖率、占位符、回退。

界面里写错的键不会报错，只会显示成裸露的英文键名——所以这里把整个 app 目录
（JS、HTML、Python）里出现的键全部对一遍，缺一个就失败。
"""

from __future__ import annotations

import json
import re

from app import i18n, paths

APP_DIR = paths.PACKAGE_DIR
INDEX = paths.WEB_DIR / "index.html"

DIRECT = re.compile(r'T\(\s*"([^"]+)"')
TERNARY = re.compile(r'T\(\s*[^()"?]*\?\s*"([^"]+)"\s*:\s*"([^"]+)"')
ATTR = re.compile(r'data-i18n(?:-title|-placeholder)?="([^"]+)"')


def _table() -> dict[str, str]:
    return json.loads((paths.LOCALES_DIR / "zh-CN.json").read_text(encoding="utf-8"))


def _corpus() -> str:
    """所有可能引用文案的文件拼成一份，用来判断「这个键还有没有人用」。"""
    chunks = [INDEX.read_text(encoding="utf-8")]
    for pattern in ("**/*.js", "**/*.py", "**/*.html"):
        for path in APP_DIR.glob(pattern):
            if path.name.endswith(".json"):
                continue
            try:
                chunks.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(chunks)


def _used_keys() -> set[str]:
    keys: set[str] = set()
    for path in (APP_DIR / "ui" / "web" / "js").glob("*.js"):
        text = path.read_text(encoding="utf-8")
        keys.update(DIRECT.findall(text))
        for first, second in TERNARY.findall(text):
            keys.update([first, second])
    keys.update(ATTR.findall(INDEX.read_text(encoding="utf-8")))
    return {key for key in keys if key and not key.endswith(".")}


def test_every_used_key_exists():
    table = _table()
    missing = sorted(key for key in _used_keys() if key not in table)
    assert missing == [], f"缺少文案：{missing}"


def test_dynamic_type_keys_exist():
    table = _table()
    for kind in ("line", "file", "check"):
        assert f"type.{kind}" in table


def test_no_unused_keys_left_behind():
    """键在 JS 的 T()、HTML 的 data-i18n、Python 的 i18n.t() 里出现过都算被使用。"""
    table = _table()
    corpus = _corpus()
    unused = sorted(
        key
        for key in table
        if key != "language.name"
        # 这两组是拼出来的：T("type." + 类型)、T("font." + 字体代号)
        and not key.startswith(("type.", "font."))
        and f'"{key}"' not in corpus
        and f"'{key}'" not in corpus
    )
    assert unused == [], f"没人用的文案：{unused}"


def test_language_meta():
    codes = [item["code"] for item in i18n.available()]
    assert "zh-CN" in codes
    assert "en-US" in codes
    assert all(item["label"] for item in i18n.available())


def test_locales_have_the_same_keys():
    zh = json.loads((paths.LOCALES_DIR / "zh-CN.json").read_text(encoding="utf-8"))
    en = json.loads((paths.LOCALES_DIR / "en-US.json").read_text(encoding="utf-8"))
    assert set(zh) == set(en), {
        "只在中文里": sorted(set(zh) - set(en)),
        "只在英文里": sorted(set(en) - set(zh)),
    }


def test_locales_have_the_same_placeholders():
    zh = json.loads((paths.LOCALES_DIR / "zh-CN.json").read_text(encoding="utf-8"))
    en = json.loads((paths.LOCALES_DIR / "en-US.json").read_text(encoding="utf-8"))
    for key in zh:
        placeholders = set(re.findall(r"\{(\w+)\}", zh[key]))
        assert placeholders == set(re.findall(r"\{(\w+)\}", en[key])), f"{key} 的占位符不一致"


def test_english_locale_has_no_chinese():
    en = json.loads((paths.LOCALES_DIR / "en-US.json").read_text(encoding="utf-8"))
    leftovers = {key: value for key, value in en.items() if re.search(r"[\u4e00-\u9fff]", value)}
    assert leftovers == {}, f"英文语言包里有中文：{leftovers}"


def test_unknown_key_returns_key():
    i18n.set_language("zh-CN")
    assert i18n.t("no.such.key") == "no.such.key"


def test_placeholder_substitution():
    i18n.set_language("zh-CN")
    assert i18n.t("doc.version", n=3) == "第 3 版"
    assert i18n.t("sidebar.count", n=5) == "共 5 个"


def test_placeholder_missing_value_keeps_braces():
    i18n.set_language("zh-CN")
    assert "{n}" in i18n.t("doc.version")


def test_placeholders_are_balanced():
    table = _table()
    for key, value in table.items():
        assert value.count("{") == value.count("}"), f"{key} 的花括号不成对"
