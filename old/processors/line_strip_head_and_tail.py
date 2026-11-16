def init():
    return {
        "processor_id": "line_strip_head_and_tail",
        "processor_type": "line",
        "processor_name": "去除首尾空白字符",
        "processor_desc": "去除每行首尾连续的指定空白字符。",
        "processor_args": {
            "accept_blank_chars": {
                "name": "接受的空白字符",
                "type": str,
                "description": "一个字符串，包含所有被认为是空白字符的字符。默认为空格、全角空格、制表符。",
                "default": " 　\t"
            }
        }
    }


def processor(line, accept_blank_chars):
    return line.strip(accept_blank_chars)
