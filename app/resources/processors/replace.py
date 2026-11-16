"""内置处理器：查找替换。"""

import re


def init():
    return {
        "name": "查找替换",
        "desc": "把指定的文字换成另一段文字",
        "type": "file",
        "args": {
            "find": {
                "name": "要查找的内容",
                "type": "str",
                "default": "",
                "desc": "留空则不做任何改动",
            },
            "to": {
                "name": "替换成",
                "type": "str",
                "default": "",
                "desc": "留空表示直接删掉找到的内容",
            },
            "regex": {
                "name": "按正则表达式匹配",
                "type": "bool",
                "default": False,
                "desc": "打开后「要查找的内容」按正则理解，替换文本里可以用 \\1 引用分组",
            },
            "ignore_case": {
                "name": "忽略大小写",
                "type": "bool",
                "default": False,
            },
        },
    }


def process(text, find, to, regex, ignore_case):
    if not find:
        return text
    if regex:
        flags = re.IGNORECASE if ignore_case else 0
        try:
            pattern = re.compile(find, flags)
        except re.error:
            return text
        return pattern.sub(to, text)
    if ignore_case:
        return re.sub(re.escape(find), lambda _match: to, text, flags=re.IGNORECASE)
    return text.replace(find, to)
