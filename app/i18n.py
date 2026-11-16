"""文案查表。

语言包放 ``app/locales/{语言代码}.json``，文件名就是语言代码。启动时扫描目录，
放进去什么语言就支持什么语言。缺键先回退 ``en-US``，再缺就返回键名本身，
永远不抛异常——界面出现裸露键名比崩溃好排查得多。
"""

from __future__ import annotations

import json
from functools import lru_cache

from app import paths

FALLBACK = "en-US"
_SYSTEM_LOCALE_KEYS = {
    0x0804: "zh-CN",
    0x0404: "zh-TW",
    0x0C04: "zh-HK",
    0x0409: "en-US",
    0x0809: "en-GB",
    0x0411: "ja-JP",
    0x0412: "ko-KR",
}

_language = "zh-CN"
_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}


def _read_locale(path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if isinstance(value, str)}


@lru_cache(maxsize=1)
def _catalogue() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    if paths.LOCALES_DIR.is_dir():
        for path in sorted(paths.LOCALES_DIR.glob("*.json"), key=lambda item: item.stem):
            result[path.stem] = _read_locale(path)
    return result


def available() -> list[dict[str, str]]:
    """语言列表，按文件名（语言代码）的字典序，不对任何语言特判。"""
    catalogue = _catalogue()
    return [
        {"code": code, "label": table.get("language.name", code)}
        for code, table in catalogue.items()
    ]


def codes() -> list[str]:
    return [item["code"] for item in available()]


def system_language() -> str:
    """读 Windows 界面语言。读不到就用英语。"""
    try:
        import ctypes

        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = langid & 0x3FF
        if primary == 0x04:  # 中文
            simplified = langid in (0x0804, 0x1004)
            return "zh-CN" if simplified else "zh-TW"
        return _SYSTEM_LOCALE_KEYS.get(langid, FALLBACK)
    except Exception:  # 非 Windows 或接口不可用：按规范回退英语
        return FALLBACK


def initial_language() -> str:
    """第一次启动时的界面语言：系统语言 → 英语 → 第一个可用语言包。"""
    catalogue = _catalogue()
    system = system_language()
    if system in catalogue:
        return system
    if FALLBACK in catalogue:
        return FALLBACK
    return next(iter(catalogue), "zh-CN")


def set_language(code: str) -> None:
    global _language, _strings, _fallback
    catalogue = _catalogue()
    if code not in catalogue:
        fallback_code = initial_language()
        code = fallback_code if fallback_code in catalogue else next(iter(catalogue), "zh-CN")
    _language = code
    _strings = catalogue.get(code, {})
    _fallback = catalogue.get(FALLBACK, {})


def language() -> str:
    return _language


def t(key: str, **values) -> str:
    """查表并填占位符。占位符格式统一 ``{name}``，填不上就原样留着。"""
    text = _strings.get(key) or _fallback.get(key) or key
    if not values:
        return text
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def table() -> dict[str, str]:
    """当前语言的整份键表，一次性下发给前端。"""
    merged = dict(_fallback)
    merged.update(_strings)
    return merged
