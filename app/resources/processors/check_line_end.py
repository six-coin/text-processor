"""内置处理器：检查行尾是不是允许的句末标点。"""


def init():
    return {
        "name": "检查行末标点",
        "desc": "标出行尾不是句末标点的行",
        "type": "check",
        "args": {
            "chars": {
                "name": "允许的行末字符",
                "type": "str",
                "default": "。？！…”）—：",
                "desc": "一行最后一个字符属于这里面，就算通过",
            }
        },
    }


def process(line, chars):
    stripped = line.rstrip()
    if not stripped:
        return None
    last = stripped[-1]
    if last in chars:
        return None
    return "行尾是「" + last + "」，不是句末标点"
