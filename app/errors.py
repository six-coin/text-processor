"""异常体系：一个基类 + 少量子类。

单机小工具里，异常直接携带本地化文案：界面层 ``str(error)`` 就能显示，
不必再为每个字段名写一遍映射。代价是 core 层引用了文案层，且切换语言后
已经抛出的异常文案不会跟着变——这两点在单机工具里都可以接受。
"""

from __future__ import annotations


class AppError(Exception):
    """本程序抛出的所有异常的基类。"""


class ConfigError(AppError):
    """配置缺失、读不出来、结构不合法。"""


class ProcessorError(AppError):
    """处理器脚本不合法或执行失败。"""


class ProjectError(AppError):
    """项目结构损坏、版本越界。"""
