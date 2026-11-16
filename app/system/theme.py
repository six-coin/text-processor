"""外观：只有浅色与深色，没有「跟随系统」。"""

from __future__ import annotations

import os

THEMES = ("light", "dark")
DEFAULT = "light"


def system_theme() -> str:
    """读 Windows 的应用主题偏好。读不到就回退浅色。"""
    if os.name != "nt":
        return DEFAULT
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if int(value) else "dark"
    except (OSError, ValueError, ImportError):
        return DEFAULT


def resolve(value: object) -> str:
    """空值取系统偏好；旧配置里的 system 定成当时的偏好；其余无法识别的回退浅色。"""
    if value in (None, "", "system"):
        return system_theme()
    if value == "dark":
        return "dark"
    if value == "light":
        return "light"
    return DEFAULT
