"""行内差异。

用 ``difflib.SequenceMatcher`` 找出改动片段，输出的是**片段数组**而不是 HTML——
前端拿到 ``[[文本, 是否改动], ...]`` 自己渲染，转义、主题色都由前端管。
"""

from __future__ import annotations

import difflib

#: 一次评审最多列出多少处改动。超过的部分按「全部应用」处理。
REVIEW_LIMIT = 500

Segment = list  # [text, changed]


def segments(old: str, new: str) -> tuple[list[Segment], list[Segment]]:
    """逐字比较两行，返回 (原文片段, 新文片段)，改动处标记为 1。"""
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    left: list[Segment] = []
    right: list[Segment] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            left.append([old[i1:i2], 0])
            right.append([new[j1:j2], 0])
            continue
        if i1 != i2:
            left.append([old[i1:i2], 1])
        if j1 != j2:
            right.append([new[j1:j2], 1])
    return left, right


def changed_lines(
    old_lines: list[str], new_lines: list[str], limit: int = REVIEW_LIMIT
) -> tuple[list[dict], int]:
    """列出发生改动的行。返回 (改动列表, 被省略的条数)。

    只有行数一致时才能逐行配对；行数不一致说明处理器改变了行数，由调用方
    决定怎么处理（这里按较短的配对，多出来的部分不计入评审）。
    """
    items: list[dict] = []
    total = 0
    for index in range(min(len(old_lines), len(new_lines))):
        before = old_lines[index]
        after = new_lines[index]
        if before == after:
            continue
        total += 1
        if len(items) >= limit:
            continue
        left, right = segments(before, after)
        items.append({"index": index, "before": before, "after": after, "a": left, "b": right})
    return items, max(0, total - len(items))
