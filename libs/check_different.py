import difflib
import html


def check_different(origin, destination):
    """对比两个字符串的差异，返回带有背景颜色标记的 HTML 文本"""
    origin = str(html.escape(origin))
    destination = str(html.escape(destination))
    matcher = difflib.SequenceMatcher(None, origin, destination)

    result_origin = []
    result_destination = []
    for tag, ori_start, ori_end, destination_start, destination_end in matcher.get_opcodes():
        if tag == "equal":  # 相同的部分：无背景色
            result_origin.append(origin[ori_start:ori_end])
            result_destination.append(destination[destination_start:destination_end])
        elif tag == "replace":  # 替换的部分：原始文本用红色背景，目标文本用绿色背景
            result_origin.append(_wrap_with_bg(origin[ori_start:ori_end], "#FFE6E6"))
            result_destination.append(_wrap_with_bg(destination[destination_start:destination_end], "#E6FFE6"))
        elif tag == "delete":  # 删除的部分：原始文本用红色背景
            result_origin.append(_wrap_with_bg(origin[ori_start:ori_end], "#FFE6E6"))
        elif tag == "insert":  # 插入的部分：目标文本用绿色背景
            result_destination.append(_wrap_with_bg(destination[destination_start:destination_end], "#E6FFE6"))

    # 组合结果
    colored_origin = "".join(result_origin)
    colored_destination = "".join(result_destination)
    # 添加 HTML 标记
    colored_origin = f"<html><body><p>{colored_origin}</p></body></html>"
    colored_destination = f"<html><body><p>{colored_destination}</p></body></html>"
    return colored_origin, colored_destination


def _wrap_with_bg(text, color):
    """用XML格式包装文本，添加背景颜色"""
    text = text.replace(" ", "&nbsp;")  # 防止因空格在行首不显示
    return f'<span style="background-color:{color};">{text}</span>'
