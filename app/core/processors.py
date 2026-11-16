"""处理器的加载、校验与执行。

一个处理器就是一个 ``.py`` 文件，必须定义 ``init()`` 与 ``process()``。文件名
（去掉 ``.py``）就是它的身份，界面上从不显示——用户看到的是 ``init()`` 里的
``name`` 与 ``desc``。

三种类型：

| type | process 签名 | 返回 |
|---|---|---|
| ``line`` | ``process(line, **args)`` | 处理后的这一行 |
| ``file`` | ``process(text, **args)`` | 处理后的整篇文本 |
| ``check`` | ``process(line, **args)`` | 通过返回 ``False``；有问题返回 ``True`` 或一句原因 |

处理器不是沙箱：它在进程内执行，能做本进程能做的一切。这里用静态检查挡住
网络、子进程、文件写入这几类「明显不该出现在文本处理器里」的东西，剩下的
靠用户自己挑代码。
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import keyword
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app import paths
from app.core import text as text_tools
from app.errors import ProcessorError

TYPES = ("line", "file", "check")

#: 允许导入的标准库模块。纯计算、无副作用。
ALLOWED_IMPORTS = frozenset(
    {
        "re",
        "string",
        "unicodedata",
        "math",
        "json",
        "textwrap",
        "difflib",
        "collections",
        "itertools",
        "functools",
        "typing",
        "dataclasses",
        "datetime",
        "hashlib",
        "base64",
        "html",
        "statistics",
        "decimal",
        "fractions",
        "operator",
        "copy",
        "random",
        "enum",
        "abc",
        "numbers",
        "bisect",
        "heapq",
        "struct",
        "zlib",
        "codecs",
    }
)

#: 出现即拒绝的内建调用。读写文件、动态执行、交互输入都不该出现在处理器里。
DENIED_CALLS = frozenset({"open", "eval", "exec", "compile", "__import__", "input", "breakpoint"})

_TYPE_ALIASES = {
    "str": "str",
    "string": "str",
    "text": "text",
    "multiline": "text",
    "int": "int",
    "integer": "int",
    "float": "float",
    "double": "float",
    "bool": "bool",
    "boolean": "bool",
    "choice": "choice",
    "select": "choice",
    "enum": "choice",
}
_PY_TYPES = {str: "str", int: "int", float: "float", bool: "bool"}

_NAME_RE = re.compile(r"[\s\u3000]+")


@dataclass
class Arg:
    """一个参数声明。``value`` 是已按类型转换过的默认值。"""

    id: str
    name: str
    type: str
    default: Any
    desc: str = ""
    minimum: float | None = None
    maximum: float | None = None
    options: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "desc": self.desc,
            "min": self.minimum,
            "max": self.maximum,
            "options": self.options,
        }


@dataclass
class Processor:
    id: str
    name: str
    desc: str
    type: str
    args: list[Arg]
    func: Callable[..., Any]
    source: str
    builtin: bool

    def to_dict(self, with_source: bool = True) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "desc": self.desc,
            "type": self.type,
            "args": [arg.to_dict() for arg in self.args],
            "builtin": self.builtin,
        }
        if with_source:
            payload["source"] = self.source
        return payload


# --------------------------------------------------------------------------- 校验


def _clean_name(value: Any, fallback: str, limit: int = 60) -> str:
    text = _NAME_RE.sub(" ", str(value or "")).strip()
    return text[:limit] if text else fallback


def check_source(source: str, filename: str = "<处理器>") -> None:
    """静态检查：语法、导入、危险调用。不合法抛 ``ProcessorError``。"""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        line = error.lineno or 0
        raise ProcessorError(f"第 {line} 行语法错误：{error.msg}") from error

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    raise ProcessorError(
                        f"第 {node.lineno} 行：处理器不能导入 {root}，只能用纯计算的模块"
                    )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level:
                raise ProcessorError(f"第 {node.lineno} 行：处理器不能使用相对导入")
            if root not in ALLOWED_IMPORTS:
                raise ProcessorError(
                    f"第 {node.lineno} 行：处理器不能导入 {root}，只能用纯计算的模块"
                )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in DENIED_CALLS:
                raise ProcessorError(f"第 {node.lineno} 行：处理器不能调用 {node.func.id}()")


def _normalize_type(raw: Any) -> str:
    if isinstance(raw, type):
        if raw in _PY_TYPES:
            return _PY_TYPES[raw]
        raise ProcessorError(f"不支持的参数类型 {raw.__name__}")
    key = str(raw or "").strip().lower()
    if key in _TYPE_ALIASES:
        return _TYPE_ALIASES[key]
    raise ProcessorError(
        f"不支持的参数类型 {raw!r}，可用：str / text / int / float / bool / choice"
    )


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "off", "否")
    return bool(value)


def _coerce(arg_type: str, value: Any, label: str) -> Any:
    """按声明类型转换一个值。失败抛 ``ProcessorError``。"""
    try:
        if arg_type in ("str", "text"):
            return "" if value is None else str(value)
        if arg_type == "int":
            if isinstance(value, bool):
                return int(value)
            return int(float(str(value).strip()))
        if arg_type == "float":
            return float(str(value).strip())
        if arg_type == "bool":
            return _coerce_bool(value)
    except (TypeError, ValueError) as error:
        raise ProcessorError(f"{label} 需要 {arg_type} 类型的值，收到的是 {value!r}") from error
    return value


def _parse_arg(arg_id: str, raw: Any) -> Arg:
    """解析一个参数声明。name / type / default 三个键一个都不能少。"""
    if not isinstance(raw, dict):
        raise ProcessorError(f"参数 {arg_id} 的声明必须是一个字典")
    for key in ("name", "type", "default"):
        if key not in raw:
            raise ProcessorError(f"参数 {arg_id} 缺少 {key}")
    arg_type = _normalize_type(raw.get("type"))
    name = _clean_name(raw.get("name"), "")
    if not name:
        raise ProcessorError(f"参数 {arg_id} 的 name 不能为空")
    desc = str(raw.get("desc", "") or "").strip()

    options: list[dict[str, str]] = []
    if arg_type == "choice":
        for item in raw.get("options") or []:
            if isinstance(item, dict):
                value = str(item.get("value", "")).strip()
                label = str(item.get("label", "") or value).strip()
            else:
                value = label = str(item).strip()
            if value:
                options.append({"value": value, "label": label})
        if not options:
            raise ProcessorError(f"参数 {arg_id} 是 choice 类型，必须提供 options")

    default = raw.get("default")
    if arg_type == "choice":
        allowed = [option["value"] for option in options]
        default = str(default)
        if default not in allowed:
            default = allowed[0]
    else:
        default = _coerce(arg_type, default, f"参数 {arg_id} 的默认值")

    minimum = raw.get("min")
    maximum = raw.get("max")
    if arg_type in ("int", "float"):
        minimum = None if minimum is None else _coerce(arg_type, minimum, f"参数 {arg_id} 的 min")
        maximum = None if maximum is None else _coerce(arg_type, maximum, f"参数 {arg_id} 的 max")

    return Arg(
        id=arg_id,
        name=name,
        type=arg_type,
        default=default,
        desc=desc,
        minimum=minimum,
        maximum=maximum,
        options=options,
    )


def _parse_meta(meta: Any, func: Callable[..., Any]) -> dict[str, Any]:
    if not callable(func):
        raise ProcessorError("没有找到 process() 函数")
    if not isinstance(meta, dict):
        raise ProcessorError("init() 必须返回一个字典")

    name = _clean_name(meta.get("name"), "")
    if not name:
        raise ProcessorError("init() 里的 name 不能为空")
    desc = _clean_name(meta.get("desc"), "", 120)
    if not desc:
        raise ProcessorError("init() 里的 desc 不能为空")
    if "type" not in meta:
        raise ProcessorError("init() 里缺少 type")
    kind = str(meta.get("type", "") or "").strip().lower()
    if kind not in TYPES:
        raise ProcessorError(f"type 只能是 {' / '.join(TYPES)}，收到的是 {kind or '空'}")

    raw_args = meta.get("args", {})
    if raw_args is None:
        raw_args = {}
    if not isinstance(raw_args, dict):
        raise ProcessorError("init() 里的 args 必须是一个字典")
    args = [_parse_arg(str(key), value) for key, value in raw_args.items()]
    for arg in args:
        if not arg.id.isidentifier() or keyword.iskeyword(arg.id):
            raise ProcessorError(f"参数名 {arg.id} 不是合法的 Python 标识符")

    _check_signature(func, args)
    return {"name": name, "desc": desc, "type": kind, "args": args}


def _check_signature(func: Callable[..., Any], args: list[Arg]) -> None:
    """确认 process 的签名和 args 对得上，避免「保存成功、一运行就报错」。"""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):  # 某些内建函数取不到签名，交给运行时
        return
    parameters = list(signature.parameters.values())
    positional = [
        item
        for item in parameters
        if item.kind in (item.POSITIONAL_ONLY, item.POSITIONAL_OR_KEYWORD)
    ]
    accepts_var_positional = any(item.kind == item.VAR_POSITIONAL for item in parameters)
    if not positional and not accepts_var_positional:
        raise ProcessorError("process() 至少要接受一个参数（当前这一行或整篇文本）")
    if any(item.kind == item.VAR_KEYWORD for item in parameters):
        return

    declared = {item.name for item in parameters}
    missing = [arg.id for arg in args if arg.id not in declared]
    if missing:
        raise ProcessorError(f"process() 缺少形参：{'、'.join(missing)}")

    # 反过来也要查：process 要求的必填参数，args 里没声明，运行时会直接 TypeError。
    known = {arg.id for arg in args}
    unbound = [
        item.name
        for item in positional[1:]
        if item.default is inspect.Parameter.empty and item.name not in known
    ]
    if unbound:
        raise ProcessorError(
            f"process() 需要参数 {'、'.join(unbound)}，但 init() 的 args 里没有声明"
        )


def build(source: str, processor_id: str, builtin: bool = False) -> Processor:
    """把源码编译成处理器对象。任何不合法都抛 ``ProcessorError``。"""
    check_source(source, f"{processor_id}.py")
    namespace: dict[str, Any] = {
        "__name__": f"processor_{processor_id}",
        "__file__": f"{processor_id}.py",
    }
    try:
        exec(compile(source, f"{processor_id}.py", "exec"), namespace)  # noqa: S102
    except ProcessorError:
        raise
    except Exception as error:
        raise ProcessorError(f"加载时出错：{type(error).__name__}: {error}") from error

    init = namespace.get("init")
    func = namespace.get("process")
    if not callable(init):
        raise ProcessorError("没有找到 init() 函数")

    try:
        meta = init()
    except Exception as error:
        raise ProcessorError(f"init() 执行失败：{type(error).__name__}: {error}") from error

    parsed = _parse_meta(meta, func)
    return Processor(
        id=processor_id,
        name=parsed["name"],
        desc=parsed["desc"],
        type=parsed["type"],
        args=parsed["args"],
        func=func,
        source=source,
        builtin=builtin,
    )


# --------------------------------------------------------------------------- 读写


def _builtin_ids() -> set[str]:
    if not paths.BUILTIN_PROCESSORS_DIR.is_dir():
        return set()
    return {path.stem for path in paths.BUILTIN_PROCESSORS_DIR.glob("*.py")}


def load_all() -> tuple[list[Processor], list[dict[str, str]]]:
    """读取处理器目录。返回 (可用列表, 出错列表)；单个文件出错不影响其它。"""
    builtin = _builtin_ids()
    processors: list[Processor] = []
    errors: list[dict[str, str]] = []
    folder = paths.PROCESSORS_DIR
    if not folder.is_dir():
        return processors, errors

    for path in sorted(folder.glob("*.py"), key=lambda item: item.name):
        if path.name.startswith("_"):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as error:
            errors.append({"file": path.name, "error": f"读取失败：{error}"})
            continue
        try:
            processors.append(build(source, path.stem, builtin=path.stem in builtin))
        except ProcessorError as error:
            logger.warning("处理器 {} 无法加载：{}", path.name, error)
            errors.append({"file": path.name, "error": str(error)})

    processors.sort(key=lambda item: (TYPES.index(item.type), item.name))
    return processors, errors


def save(processor_id: str, source: str) -> Processor:
    """校验并写入处理器文件。校验不过不落盘。"""
    processor = build(source, processor_id)
    paths.PROCESSORS_DIR.mkdir(parents=True, exist_ok=True)
    path = paths.PROCESSORS_DIR / f"{processor_id}.py"
    temp = path.with_suffix(".py.tmp")
    temp.write_text(source, encoding="utf-8", newline="\n")
    temp.replace(path)
    return processor


def create(source: str) -> Processor:
    """新建一个处理器，文件名自动生成。"""
    build(source, "preview")  # 先校验，避免落盘后才发现不能用
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:8]
    base = f"proc_{digest}"
    candidate = base
    counter = 2
    while (paths.PROCESSORS_DIR / f"{candidate}.py").exists():
        candidate = f"{base}{counter}"
        counter += 1
    return save(candidate, source)


def delete(processor_id: str) -> None:
    path = paths.PROCESSORS_DIR / f"{processor_id}.py"
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as error:
        raise ProcessorError(f"删除失败：{error}") from error


def restore_builtins() -> int:
    """把缺的内置处理器补回来。返回补了几个。"""
    if not paths.BUILTIN_PROCESSORS_DIR.is_dir():
        return 0
    paths.PROCESSORS_DIR.mkdir(parents=True, exist_ok=True)
    restored = 0
    for path in paths.BUILTIN_PROCESSORS_DIR.glob("*.py"):
        target = paths.PROCESSORS_DIR / path.name
        if target.exists():
            continue
        target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        restored += 1
    return restored


def seed_builtins() -> int:
    """首次启动时铺一份内置处理器。目录里已经有东西就不动。"""
    folder = paths.PROCESSORS_DIR
    if folder.is_dir() and any(folder.glob("*.py")):
        return 0
    return restore_builtins()


# --------------------------------------------------------------------------- 执行


def coerce_args(processor: Processor, raw: dict[str, Any] | None) -> dict[str, Any]:
    """把界面传来的参数收敛成处理器要的类型。缺的用默认值。"""
    raw = raw or {}
    values: dict[str, Any] = {}
    for arg in processor.args:
        if arg.id not in raw or raw[arg.id] is None:
            values[arg.id] = arg.default
            continue
        value = raw[arg.id]
        if arg.type == "choice":
            allowed = [option["value"] for option in arg.options]
            value = str(value)
            values[arg.id] = value if value in allowed else arg.default
            continue
        if arg.type == "bool":
            values[arg.id] = _coerce_bool(value)
            continue
        value = _coerce(arg.type, value, f"参数「{arg.name}」")
        if arg.type in ("int", "float"):
            if arg.minimum is not None and value < arg.minimum:
                value = arg.minimum
            if arg.maximum is not None and value > arg.maximum:
                value = arg.maximum
        values[arg.id] = value
    return values


def _call(processor: Processor, payload: str, params: dict[str, Any], line_no: int | None) -> Any:
    try:
        return processor.func(payload, **params)
    except Exception as error:
        where = f"第 {line_no} 行" if line_no is not None else "整篇文本"
        raise ProcessorError(f"{where}执行失败：{type(error).__name__}: {error}") from error


def apply(processor: Processor, text: str, params: dict[str, Any]) -> str:
    """执行处理器，返回新的整篇文本。"""
    if processor.type == "file":
        result = _call(processor, text, params, None)
        if not isinstance(result, str):
            raise ProcessorError(f"process() 应该返回字符串，实际返回了 {type(result).__name__}")
        return result

    if processor.type != "line":
        raise ProcessorError("检查类处理器不会修改文本")

    lines, trailing = text_tools.split(text)
    output: list[str] = []
    for index, line in enumerate(lines, 1):
        result = _call(processor, line, params, index)
        if not isinstance(result, str):
            raise ProcessorError(
                f"第 {index} 行：process() 应该返回字符串，实际返回了 {type(result).__name__}"
            )
        output.append(result)
    return text_tools.join(output, trailing)


def inspect_lines(processor: Processor, text: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """执行检查类处理器，返回被标记的行。"""
    lines, _ = text_tools.split(text)
    flagged: list[dict[str, Any]] = []
    for index, line in enumerate(lines, 1):
        result = _call(processor, line, params, index)
        verdict, reason = _interpret(result)
        if verdict:
            flagged.append({"index": index - 1, "reason": reason, "text": line})
    return flagged


def _interpret(result: Any) -> tuple[bool, str]:
    """把检查结果收敛成 (是否命中, 原因)。"""
    if result is None:
        return False, ""
    if isinstance(result, bool):
        return result, ""
    if isinstance(result, str):
        reason = result.strip()
        return bool(reason), reason
    if isinstance(result, (tuple, list)) and len(result) >= 1:
        reason = str(result[1]).strip() if len(result) > 1 else ""
        return bool(result[0]), reason
    return bool(result), ""


def find(processors: list[Processor], processor_id: str) -> Processor | None:
    for processor in processors:
        if processor.id == processor_id:
            return processor
    return None


def template() -> str:
    """手写处理器时的起手模板。"""
    return '''"""在这里写一句这个处理器做什么。"""


def init():
    return {
        "name": "新的处理器",
        "desc": "一句话说明它会做什么",
        "type": "line",  # line / file / check
        "args": {},
    }


def process(line):
    return line
'''
