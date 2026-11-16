"""应用级配置：读写 ``<数据目录>/app.json``。

只负责「把 JSON 读成扁平 dict」和「把 dict 原子写回去」，不缓存、不持有界面状态。
读取时夹取、未知键原样保留；结构损坏抛 ``ConfigError``，不静默重建。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app import paths
from app.errors import ConfigError
from app.system import theme

#: 允许的主题取值。只有浅色与深色，没有「跟随系统」。
THEMES = theme.THEMES

#: 正文一次最多显示多少字。0 表示不限制。
DISPLAY_LIMITS = (5000, 10000, 20000, 50000, 0)
DEFAULT_LIMIT = 10000

#: 正文预览的字号（像素）。超出范围就夹到最近的合法值。
FONT_SIZES = (13, 14.5, 16, 18, 20)
DEFAULT_FONT_SIZE = 14.5

_DEFAULT: dict[str, Any] = {
    "language": "",
    "theme": "",
    "wrap": True,
    "display_limit": DEFAULT_LIMIT,
    "font_size": DEFAULT_FONT_SIZE,
    "last_project": "",
    "recent": {},
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise ConfigError(f"读不出配置文件 {path.name}：{error}") from error
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        message = f"配置文件 {path.name} 不是合法的 JSON（第 {error.lineno} 行）"
        raise ConfigError(message) from error
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件 {path.name} 的顶层必须是一个对象")
    return data


def coerce_display_limit(value: object) -> int:
    """夹到允许的档位；认不出来就用默认值。"""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    if number <= 0:
        return 0
    return min(DISPLAY_LIMITS) if number < min(DISPLAY_LIMITS) else number


def coerce_font_size(value: object) -> float:
    """夹到 12–24 之间；认不出来就用默认值。"""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_FONT_SIZE
    if not 12 <= number <= 24:
        return DEFAULT_FONT_SIZE
    return round(number, 1)


def _write_json(path: Path, payload: Any) -> None:
    """临时文件 + ``os.replace``：中途崩溃不会留下半个文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4, ensure_ascii=False)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


class Settings:
    """一份配置的内存视图。改动只在 ``save()`` 时落盘。"""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or paths.APP_CONFIG_PATH
        self._raw: dict[str, Any] = {}
        self._data: dict[str, Any] = dict(_DEFAULT)

    def load(self) -> dict[str, Any]:
        self._raw = _read_json(self._path)
        self._data = dict(_DEFAULT)
        self._data.update(self._normalize(self._raw))
        if not self._path.exists():
            # 首次启动就写一份可用内容，用户不需要先手写 JSON。
            self.save()
        return self._data

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        language = str(raw.get("language", "") or "").strip()
        if language:
            data["language"] = language
        data["theme"] = theme.resolve(raw.get("theme"))
        data["wrap"] = bool(raw.get("wrap", True))
        data["display_limit"] = coerce_display_limit(raw.get("display_limit"))
        data["font_size"] = coerce_font_size(raw.get("font_size"))
        data["last_project"] = str(raw.get("last_project", "") or "").strip()
        recent = raw.get("recent")
        data["recent"] = recent if isinstance(recent, dict) else {}
        return data

    def save(self) -> None:
        merged = dict(self._raw)
        merged.update({key: value for key, value in self._data.items() if key != "recent"})
        merged["recent"] = self._data.get("recent") or {}
        # 空语言不写盘：让下次启动重新按系统语言决定。
        if not merged.get("language"):
            merged.pop("language", None)
        _write_json(self._path, merged)
        self._raw = merged

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if key in _DEFAULT:
                self._data[key] = value

    def as_dict(self) -> dict[str, Any]:
        return {
            "language": self._data.get("language") or "",
            "theme": self._data.get("theme") or theme.DEFAULT,
            "wrap": bool(self._data.get("wrap", True)),
            "display_limit": int(self._data.get("display_limit", DEFAULT_LIMIT)),
            "font_size": float(self._data.get("font_size", DEFAULT_FONT_SIZE)),
        }

    def recent_for(self, processor_id: str) -> dict[str, Any]:
        recent = self._data.get("recent") or {}
        entry = recent.get(processor_id)
        return entry if isinstance(entry, dict) else {}

    def remember(self, processor_id: str, params: dict[str, Any], compare: bool) -> None:
        recent = dict(self._data.get("recent") or {})
        recent[processor_id] = {"params": params, "compare": bool(compare)}
        # 只留最近 40 个处理器的参数，避免配置无限增长。
        if len(recent) > 40:
            for key in list(recent)[: len(recent) - 40]:
                recent.pop(key, None)
        self._data["recent"] = recent
