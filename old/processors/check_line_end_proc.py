def init():
    return {
        "processor_id": "check_line_end_proc",
        "processor_type": "check",
        "processor_name": "检查行尾标点符号",
        "processor_desc": "检查所有行尾标点符号不符合要求的行。",
        "processor_args": {
            "accept_line_end_proc_chars": {
                "name": "接受的行末标点字符",
                "type": str,
                "description": "一个字符串，包含所有被认为是合法的行末标点的字符。",
                "default": "。？！”）—…："
            }
        }
    }


def processor(line, accept_line_end_proc_chars):
    return not line[-1] in accept_line_end_proc_chars
