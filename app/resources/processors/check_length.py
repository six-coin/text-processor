"""内置处理器：检查过长的行。"""


def init():
    return {
        "name": "检查行长度",
        "desc": "标出字数超过上限的行",
        "type": "check",
        "args": {
            "limit": {
                "name": "字数上限",
                "type": "int",
                "default": 80,
                "min": 1,
                "max": 10000,
                "desc": "一行的字符数超过这个值就会被标出来",
            }
        },
    }


def process(line, limit):
    count = len(line)
    if count <= limit:
        return None
    return "本行 " + str(count) + " 字，超出上限 " + str(limit) + " 字"
