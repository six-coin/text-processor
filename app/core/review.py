"""待确认的改动。

处理器执行完但还没落盘时，结果先存在这里，等用户逐行决定「应用 / 保留」。
状态只放内存：进程退出即作废，正好符合「没确认的改动不该留下痕迹」。
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

#: 同时最多挂起几份。超过就丢最旧的——用户不可能同时确认八份改动。
LIMIT = 8


@dataclass
class Pending:
    token: str
    project_id: str
    title: str
    kind: str  # "line" 或 "check"
    old_text: str
    trailing: bool
    #: line 模式：与原文逐行对应的新行。check 模式：空列表。
    new_lines: list[str] = field(default_factory=list)
    #: 需要用户决定的行：[{index, before, after, a, b}] 或 [{index, reason, text}]
    items: list[dict[str, Any]] = field(default_factory=list)
    #: 因为超出上限而没有列出的改动条数
    omitted: int = 0


class Store:
    """内存里的一张待确认表。"""

    def __init__(self, limit: int = LIMIT) -> None:
        self._items: dict[str, Pending] = {}
        self._order: list[str] = []
        self._limit = limit

    def put(self, pending: Pending) -> Pending:
        if not pending.token:
            pending.token = secrets.token_hex(8)
        self._items[pending.token] = pending
        self._order.append(pending.token)
        while len(self._order) > self._limit:
            oldest = self._order.pop(0)
            self._items.pop(oldest, None)
        return pending

    def get(self, token: str) -> Pending | None:
        return self._items.get(token)

    def drop(self, token: str) -> None:
        self._items.pop(token, None)
        if token in self._order:
            self._order.remove(token)
