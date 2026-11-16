"""内置处理器：去除每行首尾的指定字符。"""


def init():
    return {
        "name": "去除首尾空白",
        "desc": "去掉每行开头和结尾的空白字符",
        "type": "line",
        "args": {
            "chars": {
                "name": "视为空白的字符",
                "type": "str",
                "default": " \u3000\t",
                "desc": "这些字符出现在行首或行尾时会被删掉",
            }
        },
    }


def process(line, chars):
    return line.strip(chars)
