"""单实例互斥量与窗口唤醒。

每个入口一个命名互斥量。用 ``Local\\`` 而不是 ``Global\\``：只在当前登录会话内
生效，多用户互不干扰。拿到锁之后整个进程生命周期都持有。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from loguru import logger

MUTEX = "Local\\SixCoin.TextProcessor.Main"

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype = wintypes.BOOL

_user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
_user32.FindWindowW.restype = wintypes.HWND
_user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.ShowWindow.restype = wintypes.BOOL
_user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.BringWindowToTop.argtypes = (wintypes.HWND,)
_user32.BringWindowToTop.restype = wintypes.BOOL


class InstanceLock:
    """命名互斥量。``acquire()`` 返回 False 表示已经有实例在跑。"""

    def __init__(self, name: str = MUTEX) -> None:
        self._name = name
        self._handle: int | None = None

    def acquire(self) -> bool:
        handle = _kernel32.CreateMutexW(None, True, self._name)
        if not handle:
            logger.error("创建互斥量 {} 失败：{}", self._name, ctypes.get_last_error())
            return False
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            self._handle = None


def activate_window(title: str) -> bool:
    """把标题匹配的窗口提到前面。找不到就返回 False。"""
    handle = _user32.FindWindowW(None, title)
    if not handle:
        return False
    _user32.ShowWindow(handle, SW_RESTORE)
    _user32.BringWindowToTop(handle)
    _user32.SetForegroundWindow(handle)
    return True
