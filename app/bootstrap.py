"""启动期的公共步骤。

每个入口第一件事都是 ``bootstrap.prepare()``：建目录、铺内置处理器、把搬迁
警告交给日志。它不做任何界面相关的事。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

from app import paths
from app.core import processors


def prepare() -> list[str]:
    """建目录、铺内置处理器，返回需要写进日志的警告。"""
    warnings: list[str] = list(paths.MIGRATION_WARNINGS)
    if paths.MIGRATED_ITEMS:
        warnings.append(f"数据目录已迁移 {paths.MIGRATED_ITEMS} 项到 {paths.DATA_DIR}")
    for folder in (
        paths.DATA_DIR,
        paths.LOCAL_DIR,
        paths.LOG_DIR,
        paths.LOCK_DIR,
        paths.PROJECTS_DIR,
        paths.PROCESSORS_DIR,
        paths.TEMP_DIR,
    ):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            warnings.append(f"无法创建 {folder}：{error}")
    try:
        seeded = processors.seed_builtins()
        if seeded:
            logger.info("已铺开 {} 个内置处理器", seeded)
    except OSError as error:
        warnings.append(f"内置处理器写入失败：{error}")
    return warnings


def is_first_run() -> bool:
    """数据目录里还没有主配置文件，就是第一次运行。"""
    return not paths.APP_CONFIG_PATH.exists()


def pythonw() -> Path:
    return paths.PYTHONW if paths.PYTHONW.is_file() else Path(sys.executable)


def fatal(message: str) -> None:
    """启动阶段的致命错误：没有界面可用，只能弹窗。"""
    from app import logging_setup

    logging_setup.fatal(message)


def environment_note() -> str:
    """写进日志的一行环境信息。"""
    return (
        f"程序目录={paths.PROGRAM_DIR} 数据目录={paths.DATA_DIR} "
        f"本地目录={paths.LOCAL_DIR} 临时目录={paths.TEMP_DIR} 系统={os.name}"
    )
