"""窗口装配与启动。

单实例 → 日志 → 建目录 → 造 API → 开窗。窗口标题保持固定，多开时靠它把
已有窗口提到前面。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading

import webview
from loguru import logger

from app import bootstrap, i18n, logging_setup, paths, settings
from app.system import single
from app.ui.api import Api

#: 窗口占屏幕的比例，以及夹取后的上下限（像素）。
WIDTH_RATIO = 0.86
HEIGHT_RATIO = 0.84
MIN_SIZE = (1000, 620)
MAX_WIDTH = 1680
MAX_HEIGHT = 1000


def _screen_size() -> tuple[int, int]:
    """主屏可用分辨率。取不到就按 1920×1080 算。"""
    try:
        user32 = ctypes.windll.user32
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
        if width > 0 and height > 0:
            return width, height
    except Exception:  # 非 Windows 或接口不可用
        pass
    return 1920, 1080


def _geometry() -> tuple[int, int, int, int]:
    screen_w, screen_h = _screen_size()
    width = int(min(max(screen_w * WIDTH_RATIO, MIN_SIZE[0]), MAX_WIDTH))
    height = int(min(max(screen_h * HEIGHT_RATIO, MIN_SIZE[1]), MAX_HEIGHT))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    return width, height, x, y


def _activate_existing() -> None:
    """第二个实例：把已有窗口提到前面，然后安静退出。

    多开的意思就是「让我看到那个窗口」，窗到前台就够了。提不上来（窗口标题对
    不上、被别的会话占用）也只留一条日志：双击完弹一个框只会让人以为出了故障。
    """
    try:
        data = settings.Settings().load()
        i18n.set_language(str(data.get("language") or i18n.initial_language()))
    except Exception:  # 配置坏了也要能把标题说对
        i18n.set_language(i18n.initial_language())
    if single.activate_window(i18n.t("app.title")):
        return
    # 提不上来也要留一条记录：「双击了没反应」是最难解释的现象。
    logging_setup.setup("main")
    logger.warning("已有实例在运行，但没能把窗口提到前面")


def _dark_mode() -> bool:
    from app.system import theme

    return theme.system_theme() == "dark"


def main() -> int:
    lock = single.InstanceLock()
    if not lock.acquire():
        _activate_existing()
        return 0

    logging_setup.setup("main")
    try:
        for warning in bootstrap.prepare():
            logger.warning(warning)
        logger.info(bootstrap.environment_note())

        api = Api()
        width, height, x, y = _geometry()
        window = webview.create_window(
            i18n.t("app.title"),
            url=str(paths.WEB_DIR / "index.html"),
            js_api=api,
            width=width,
            height=height,
            x=x,
            y=y,
            min_size=MIN_SIZE,
            background_color="#14161a" if _dark_mode() else "#f0f2f5",
            text_select=True,
        )
        if window is None:
            logger.error("窗口创建失败")
            return 1
        api.attach(window)

        def on_closing() -> bool:
            if api.allow_close():
                return True
            threading.Thread(target=api.ask_close, daemon=True).start()
            return False

        window.events.closing += on_closing
        logger.info("窗口已创建：{}×{}", width, height)
        webview.start(debug=bool(os.environ.get("TP_DEBUG")), http_server=True)

        if api.wants_restart():
            # 先放锁再拉新进程，否则新进程会以为自己不是唯一实例。
            lock.release()
            logger.info("按用户要求重启")
            try:
                subprocess.Popen(
                    [str(bootstrap.pythonw()), str(paths.ENTRY_MAIN)],
                    cwd=str(paths.PROGRAM_DIR),
                    close_fds=True,
                )
            except OSError as error:
                logger.error("重启失败：{}", error)
                logging_setup.info(i18n.t("settings.data.restart_failed", error=error))
            return 0

        logger.info("程序正常退出")
        return 0
    except Exception as error:
        logger.exception("启动失败")
        logging_setup.fatal(i18n.t("fatal.unexpected", error=error))
        return 1
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
