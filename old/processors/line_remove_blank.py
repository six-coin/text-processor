def init():
    return {
        "processor_id": "line_remove_blank",
        "processor_type": "file",
        "processor_name": "移除空行",
        "processor_desc": "移除所有由指定的空白字符组成的行。",
        "processor_args": {
            "accept_blank_chars": {
                "name": "接受的空白字符",
                "type": str,
                "description": "一个字符串，包含所有被认为是空白字符的字符。默认为空格、全角空格、制表符。",
                "default": " 　\t"
            }
        }
    }


def processor(file, accept_blank_chars):
    result = ""
    for line in file.splitlines():
        if not all(char in accept_blank_chars for char in line):
            result += line + "\n"
    return result
