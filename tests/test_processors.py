"""处理器契约：加载、校验、执行、参数收敛。"""

from __future__ import annotations

import pytest

from app import paths
from app.core import processors
from app.errors import ProcessorError

LINE_OK = """
def init():
    return {
        "name": "去空格",
        "desc": "去掉行首尾空格",
        "type": "line",
        "args": {"chars": {"name": "字符", "type": "str", "default": " "}},
    }


def process(line, chars):
    return line.strip(chars)
"""

CHECK_OK = """
def init():
    return {"name": "查长度", "desc": "太长就报", "type": "check",
            "args": {"limit": {"name": "上限", "type": "int", "default": 3, "min": 1, "max": 99}}}


def process(line, limit):
    if len(line) > limit:
        return "超了"
    return None
"""

FILE_OK = """
def init():
    return {"name": "拼接", "desc": "接起来", "type": "file", "args": {}}


def process(text):
    return text.replace("\\n", "|")
"""


def test_builtin_processors_all_load():
    processors.restore_builtins()
    loaded, errors = processors.load_all()
    assert errors == []
    names = {item.name for item in loaded}
    assert "去除首尾空白" in names
    assert all(item.type in processors.TYPES for item in loaded)


def test_line_processor_runs():
    item = processors.build(LINE_OK, "demo")
    assert processors.apply(item, "  a  \n b ", {"chars": " "}) == "a\nb"


def test_check_processor_reports_reason():
    item = processors.build(CHECK_OK, "demo")
    flags = processors.inspect_lines(item, "abcde\nab\n", {"limit": 3})
    assert len(flags) == 1
    assert flags[0]["index"] == 0
    assert flags[0]["reason"] == "超了"


def test_file_processor_runs():
    item = processors.build(FILE_OK, "demo")
    assert processors.apply(item, "a\nb", {}) == "a|b"


def test_bad_type_rejected():
    source = LINE_OK.replace('"type": "line"', '"type": "magic"')
    with pytest.raises(ProcessorError, match="type"):
        processors.build(source, "demo")


def test_missing_process_rejected():
    with pytest.raises(ProcessorError, match="process"):
        processors.build('def init():\n    return {"name":"x","desc":"y","type":"line"}\n', "demo")


def test_syntax_error_reports_line():
    with pytest.raises(ProcessorError, match="语法错误"):
        processors.build("def init(:\n    pass\n", "demo")


def test_denied_import_rejected():
    source = "import subprocess\n" + LINE_OK
    with pytest.raises(ProcessorError, match="subprocess"):
        processors.build(source, "demo")


def test_denied_call_rejected():
    source = LINE_OK.replace("return line.strip(chars)", "return open(chars).read()")
    with pytest.raises(ProcessorError, match="open"):
        processors.build(source, "demo")


def test_signature_mismatch_rejected():
    source = LINE_OK.replace("def process(line, chars):", "def process(line):")
    with pytest.raises(ProcessorError, match="形参"):
        processors.build(source, "demo")


def test_arg_coercion_clamps():
    item = processors.build(CHECK_OK, "demo")
    values = processors.coerce_args(item, {"limit": "1000"})
    assert values["limit"] == 99
    values = processors.coerce_args(item, {"limit": "-5"})
    assert values["limit"] == 1
    values = processors.coerce_args(item, {})
    assert values["limit"] == 3


def test_non_string_return_rejected():
    source = LINE_OK.replace("return line.strip(chars)", "return 1")
    item = processors.build(source, "demo")
    with pytest.raises(ProcessorError, match="字符串"):
        processors.apply(item, "a", {"chars": " "})


def test_broken_file_does_not_break_loading():
    processors.restore_builtins()
    (paths.PROCESSORS_DIR / "broken.py").write_text("def init(:\n", encoding="utf-8")
    loaded, errors = processors.load_all()
    assert loaded
    assert len(errors) == 1
    assert errors[0]["file"] == "broken.py"


def test_create_and_delete():
    item = processors.create(LINE_OK)
    assert (paths.PROCESSORS_DIR / f"{item.id}.py").exists()
    processors.delete(item.id)
    assert not (paths.PROCESSORS_DIR / f"{item.id}.py").exists()


def test_save_does_not_write_invalid_source():
    item = processors.create(LINE_OK)
    with pytest.raises(ProcessorError):
        processors.save(item.id, "def init(:\n")
    assert "def init():" in (paths.PROCESSORS_DIR / f"{item.id}.py").read_text(encoding="utf-8")


def test_template_is_valid():
    item = processors.build(processors.template(), "tpl")
    assert item.type == "line"


def test_missing_desc_rejected():
    source = LINE_OK.replace('        "desc": "去掉行首尾空格",\n', "")
    with pytest.raises(ProcessorError, match="desc"):
        processors.build(source, "demo")


def test_missing_arg_name_rejected():
    source = LINE_OK.replace(
        '{"name": "字符", "type": "str", "default": " "}', '{"type": "str", "default": " "}'
    )
    with pytest.raises(ProcessorError, match="缺少 name"):
        processors.build(source, "demo")


def test_missing_arg_default_rejected():
    source = LINE_OK.replace('"default": " "', '"desc": "x"')
    with pytest.raises(ProcessorError, match="缺少 default"):
        processors.build(source, "demo")


def test_missing_arg_type_rejected():
    source = LINE_OK.replace('"type": "str", ', "")
    with pytest.raises(ProcessorError, match="缺少 type"):
        processors.build(source, "demo")


def test_undeclared_process_param_rejected():
    """process 要的参数没在 args 里声明，运行时必然 TypeError，必须在保存时挡住。"""
    source = LINE_OK.replace('"args": {"chars"', '"args": {"other"').replace(
        "def process(line, chars):", "def process(line, chars):"
    )
    with pytest.raises(ProcessorError):
        processors.build(source, "demo")


def test_extra_required_param_rejected():
    source = CHECK_OK.replace(
        '"args": {"limit": {"name": "上限", "type": "int", "default": 3, "min": 1, "max": 99}}',
        '"args": {}',
    )
    with pytest.raises(ProcessorError, match="没有声明"):
        processors.build(source, "demo")


def test_optional_process_param_is_fine():
    source = CHECK_OK.replace("def process(line, limit):", "def process(line, limit=5):").replace(
        '"args": {"limit": {"name": "上限", "type": "int", "default": 3, "min": 1, "max": 99}}',
        '"args": {}',
    )
    item = processors.build(source, "demo")
    assert item.type == "check"
