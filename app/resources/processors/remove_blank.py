"""内置处理器：移除整行都是空白字符的行。"""


def init():
    return {
        "name": "移除空行",
        "desc": "删掉只由空白字符组成的行",
        "type": "file",
        "args": {
            "chars": {
                "name": "视为空白的字符",
                "type": "str",
                "default": " \u3000\t",
                "desc": "一行里只有这些字符时，这一行会被删除",
            }
        },
    }


def process(text, chars):
    kept = []
    for line in text.splitlines():
        if not line or all(char in chars for char in line):
            continue
        kept.append(line)
    return "\n".join(kept)
