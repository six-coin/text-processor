"""日志与致命错误。

日志写本地目录，每次启动一个新文件，文件名带时间戳——出问题时能一眼定位
是哪一次运行。崩溃弹窗统一三段：出了什么事、发生时间、日志在哪。
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from loguru import logger

from app import i18n, paths

_LOG_FORMAT = "[{level}] [{time:YYYY-MM-DD HH:mm:ss}] {message}"
_log_file: Path | None = None


def setup(name: str) -> Path:
    global _log_file
    paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
    _log_file = paths.LOG_DIR / f"{name}_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"

    logger.remove()
    logger.add(
        str(_log_file),
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        # 默认会把局部变量全打进日志，密钥会跟着泄露。
        diagnose=False,
        rotation="5 MB",
        retention="14 days",
        format=_LOG_FORMAT,
    )

    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    return _log_file


def log_path() -> Path | None:
    return _log_file


def _excepthook(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("未捕获的异常")
    fatal(i18n.t("fatal.unexpected", error=f"{exc_type.__name__}: {exc_value}"))


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).critical(
        "线程 {} 中未捕获的异常", args.thread.name if args.thread else "未知"
    )


def fatal(message: str) -> None:
    """致命错误：刷完日志、弹窗告知、立刻退出。"""
    try:
        logger.critical(message)
        logger.complete()
    except Exception:  # 日志系统本身坏了也必须能退出
        pass

    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, crash_text(message), i18n.t("app.title"), 0x10)
        except Exception:  # 弹窗失败时只能静默退出
            pass
    os._exit(1)


def crash_text(message: str) -> str:
    """崩溃弹窗的正文：错误、时间、日志位置。"""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    where = str(_log_file or paths.LOG_DIR)
    return (
        f"{message}\n\n"
        f"{i18n.t('fatal.time_line', value=stamp)}\n"
        f"{i18n.t('fatal.log_line', value=where)}"
    )


def info(message: str, title: str = "") -> None:
    """信息框（``0x40``）。多开、需要用户知道但不致命的事情用它。"""
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            None, str(message), title or i18n.t("app.title"), 0x40 | 0x10000
        )
    except Exception:  # 弹窗失败时没有别的出口
        pass
