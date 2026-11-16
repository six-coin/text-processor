"""剪贴板与资源管理器。

WebView 里 ``navigator.clipboard`` 在非安全上下文不可靠，统一走 Win32。
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from loguru import logger

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.OpenClipboard.argtypes = (wintypes.HWND,)
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.EmptyClipboard.restype = wintypes.BOOL
_user32.CloseClipboard.restype = wintypes.BOOL
_user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
_user32.SetClipboardData.restype = wintypes.HANDLE
_kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
_kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
_kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
_kernel32.GlobalLock.restype = wintypes.LPVOID
_kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
_kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)


def copy_text(text: str) -> bool:
    """把文本放进剪贴板。失败返回 False，调用方负责提示。"""
    if os.name != "nt":
        return False
    payload = str(text)
    if not _user32.OpenClipboard(None):
        return False
    handle = None
    try:
        _user32.EmptyClipboard()
        buffer = payload.encode("utf-16-le") + b"\x00\x00"
        handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(buffer))
        if not handle:
            return False
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            return False
        try:
            ctypes.memmove(pointer, buffer, len(buffer))
        finally:
            _kernel32.GlobalUnlock(handle)
        if not _user32.SetClipboardData(CF_UNICODETEXT, handle):
            return False
        handle = None  # 交给系统，不要再 GlobalFree
        return True
    except OSError as error:  # 剪贴板被别的程序占用是常见情况，记日志即可
        logger.warning("写剪贴板失败：{}", error)
        return False
    finally:
        if handle:
            _kernel32.GlobalFree(handle)
        _user32.CloseClipboard()


def open_path(path: str) -> bool:
    """用系统默认程序打开文件或目录。"""
    try:
        os.startfile(str(path))
        return True
    except OSError as error:
        logger.warning("打开 {} 失败：{}", path, error)
        return False
