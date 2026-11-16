"""文本的行级工具。

只做两件事：把整篇文本切成行并记住「末尾有没有换行」，以及把行拼回整篇文本。
行处理器只看到单行，换行符由这里统一处理，处理器不需要关心。
"""

from __future__ import annotations


def stats(text: str) -> dict[str, int]:
    """字符数与行数。空文本是 0 行，不是 1 行。"""
    return {"chars": len(text), "lines": len(text.splitlines())}


def split(text: str) -> tuple[list[str], bool]:
    """切成行，并返回原文末尾是否有换行。

    ``str.splitlines()`` 认得 ``\\r\\n``、``\\r``、``\\n``，所以 Windows 换行的
    文件也能正确切分；拼回去时统一用 ``\\n``。
    """
    return text.splitlines(), text.endswith(("\n", "\r"))


def join(lines: list[str], trailing_newline: bool) -> str:
    """把行拼回整篇文本。``trailing_newline`` 为真时补一个换行。"""
    body = "\n".join(lines)
    if trailing_newline and body:
        return body + "\n"
    return body
