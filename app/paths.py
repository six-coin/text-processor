"""全部内部路径的唯一来源。

四类位置，职责分开：

| 位置 | 内容 | 默认 |
|---|---|---|
| 程序目录 | 代码与随程序分发的资源，只读 | 仓库根目录 |
| 数据目录 | 用户数据：项目、处理器、设置 | ``%PROGRAMDATA%\\six-coin\\text-processor`` |
| 本地目录 | 日志、锁、数据目录指针 | ``%LOCALAPPDATA%\\six-coin\\text-processor`` |
| 临时目录 | 可随时丢弃的中间文件 | ``%TEMP%\\six-coin\\text-processor`` |

本模块只负责「路径在哪」，不判断文件是否存在，也不读写业务数据。
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

VENDOR = "six-coin"
PROJECT = "text-processor"

PACKAGE_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = PACKAGE_DIR.parent
WEB_DIR = PACKAGE_DIR / "ui" / "web"
RESOURCE_DIR = PACKAGE_DIR / "resources"
BUILTIN_PROCESSORS_DIR = RESOURCE_DIR / "processors"
LOCALES_DIR = PACKAGE_DIR / "locales"
README_DIR = PROGRAM_DIR / "docs" / "readme"

_ENV_DATA = "SIXCOIN_DATA_DIR"
_ENV_LOCAL = "SIXCOIN_LOCAL_DIR"
_ENV_TEMP = "SIXCOIN_TEMP_DIR"


def _system_dir(variable: str, fallback: str) -> Path:
    raw = os.environ.get(variable, "").strip()
    return Path(raw) if raw else Path(fallback)


LOCAL_DIR = Path(
    os.environ.get(_ENV_LOCAL, "").strip()
    or _system_dir("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")) / VENDOR / PROJECT
)
TEMP_DIR = Path(
    os.environ.get(_ENV_TEMP, "").strip() or Path(tempfile.gettempdir()) / VENDOR / PROJECT
)
DATA_DIR_DEFAULT = _system_dir("PROGRAMDATA", "C:/ProgramData") / VENDOR / PROJECT

LOG_DIR = LOCAL_DIR / "logs"
LOCK_DIR = LOCAL_DIR / "locks"
DATA_POINTER = LOCAL_DIR / "data-dir.txt"
#: 「更改数据目录」留下的待搬迁标记。指针只在搬完之后才改。
DATA_PENDING = LOCAL_DIR / "data-dir.pending"


def normalize_data_dir(raw: str, base: Path | None = None) -> Path:
    """收敛成绝对路径，并保证最后一层是项目代号。

    选 ``D:////Data`` 时落点是 ``D:////Data////text-processor``；已经以它结尾就原样用
    （比较不分大小写）。相对路径以 ``base``（默认是默认数据目录）为基准。
    """
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    if not text:
        return DATA_DIR_DEFAULT
    path = Path(os.path.expandvars(text)).expanduser()
    if not path.is_absolute():
        path = (base or DATA_DIR_DEFAULT) / path
    path = Path(os.path.normpath(str(path)))
    if path.name.lower() != PROJECT:
        path = path / PROJECT
    return path


def read_data_dir() -> Path:
    """读数据目录指针；没设过、读不出来、不是绝对路径都回退默认值。"""
    override = os.environ.get(_ENV_DATA, "").strip()
    if override:
        return Path(override)
    try:
        text = DATA_POINTER.read_text(encoding="utf-8").strip()
    except OSError:
        return DATA_DIR_DEFAULT
    if not text:
        return DATA_DIR_DEFAULT
    path = Path(text)
    return path if path.is_absolute() else DATA_DIR_DEFAULT


def write_data_dir(path: Path) -> None:
    """把新的数据目录写进指针文件。下次启动才生效。"""
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    temp = DATA_POINTER.with_suffix(".tmp")
    temp.write_text(str(path), encoding="utf-8", newline="\n")
    os.replace(temp, DATA_POINTER)


def resolve_user_path(raw: str) -> Path:
    """用户输入的路径：去引号、统一反斜杠；相对路径以数据目录为基准。"""
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    if os.name == "nt":
        text = text.replace("/", "\\")
    text = text.strip()
    if not text:
        return DATA_DIR
    path = Path(text)
    return path if path.is_absolute() else (DATA_DIR / path).resolve()


def lock_for(path: Path) -> Path:
    """数据文件对应的锁文件。锁放本地目录，不跟数据混在一起。"""
    return LOCK_DIR / f"{path.parent.name}-{path.stem}.lock"


def pending_data_dir() -> Path | None:
    """上次「更改数据目录」记下的落点；没有就是 ``None``。"""
    try:
        text = DATA_PENDING.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else None


def request_data_dir(raw: str, base: Path | None = None) -> Path:
    """记下新的数据目录，等下次启动搬过去；改回当前目录只清标记。"""
    target = normalize_data_dir(raw, base)
    current = read_data_dir()
    # 少了项目代号的历史指针会让 normalize 算出一个「当前目录的子目录」；那不是
    # 用户想换地方，只是同一处地方的另一种写法，按「没有变化」处理。
    if _same_dir(target, current) or _same_dir(target, normalize_data_dir(str(current))):
        clear_pending_data_dir()
        return current
    if is_nested(target, current):
        raise OSError(f"不能把数据目录放进当前数据目录里面：{current}")
    _ensure_writable(target)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    temp = DATA_PENDING.with_suffix(".tmp")
    temp.write_text(str(target), encoding="utf-8", newline="\n")
    os.replace(temp, DATA_PENDING)
    return target


def clear_pending_data_dir() -> None:
    """丢掉待搬迁标记。"""
    try:
        DATA_PENDING.unlink()
    except OSError:
        pass


def _same_dir(left: Path, right: Path) -> bool:
    """Windows 路径不分大小写，比较前统一成规范形式。"""
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(
        os.path.normpath(str(right))
    )


def is_nested(inner: Path, outer: Path) -> bool:
    """``inner`` 是否在 ``outer`` 里（含相等）。比较不分大小写。"""
    left = os.path.normcase(os.path.normpath(str(inner)))
    right = os.path.normcase(os.path.normpath(str(outer)))
    if left == right:
        return True
    return left.startswith(right.rstrip("\\/") + os.sep)


def _ensure_writable(target: Path) -> None:
    """目标目录建得出来、写得进去，否则当场抛 ``OSError``。"""
    target.mkdir(parents=True, exist_ok=True)
    probe = target / ".sixcoin-write-probe"
    probe.write_text("", encoding="utf-8")
    probe.unlink()


def _move_item(item: Path, destination: Path) -> None:
    """搬一项到目标位置；只读属性挡路时先去掉再搬一次。

    用户的数据目录里常有只读文件（从光盘、别人机器上拷来的文稿）。
    跨盘搬迁时 ``shutil.move`` 是先复制再删源，删一个只读文件会得到「拒绝访问」，
    整次搬迁就卡在第一个文件上：数据还留在旧目录，指针却已经指向新目录。
    """
    try:
        shutil.move(str(item), str(destination))
    except PermissionError:
        _clear_read_only(item)
        # 上一次可能已经复制了一半：先清掉残骸。留着它，``shutil.move`` 会把源
        # 目录整个塞进这个同名目录，数据落到 <目标>/<名字>/<名字>。
        _remove_partial(destination)
        shutil.move(str(item), str(destination))


def _remove_partial(path: Path) -> None:
    """清掉上一次搬到一半留下的残骸（目标里本来没有这一项，出现了就是残骸）。"""
    if not path.exists():
        return
    _clear_read_only(path)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        return
    try:
        path.unlink()
    except OSError:
        pass


def _clear_read_only(path: Path) -> None:
    """把只读位清掉，目录往下递归。"""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    if path.is_dir():
        for child in path.iterdir():
            _clear_read_only(child)


def _move_contents(source: Path, target: Path) -> tuple[list[str], int]:
    """把 ``source`` 里的东西搬到 ``target``；目标已有的同名项不覆盖。"""
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return [f"无法创建 {target}：{error}"], 0
    if not source.is_dir():
        return [], 0
    warnings: list[str] = []
    moved = 0
    for item in list(source.iterdir()):
        if item.suffix == ".lock":
            # 锁恒在本地目录，数据目录里的锁文件没有搬运价值。
            try:
                item.unlink()
            except OSError:
                pass
            continue
        destination = target / item.name
        if destination.exists():
            continue
        try:
            _move_item(item, destination)
        except OSError as error:
            warnings.append(f"迁移 {item.name} 失败：{error}")
            continue
        moved += 1
    try:
        source.rmdir()
    except OSError:
        pass
    return warnings, moved


def _reconcile_data_dir() -> None:
    """启动时收敛数据目录：执行待搬迁标记，并修正没补项目代号的旧指针。

    测试用 ``SIXCOIN_DATA_DIR`` 指定了目录，一律不碰。
    """
    global MIGRATION
    if os.environ.get(_ENV_DATA, "").strip():
        return
    source = read_data_dir()
    pending = pending_data_dir()
    # 待搬迁标记写的是「当前目录的规范化形式」时不算换地方：那是同一处地方的
    # 另一种写法，硬搬只会搬进它自己的子目录。
    if pending is not None and (
        _same_dir(pending, source) or _same_dir(pending, normalize_data_dir(str(source)))
    ):
        clear_pending_data_dir()
        _record_migration("same", source, pending)
        return
    target = pending or normalize_data_dir(str(source))
    if _same_dir(target, source):
        clear_pending_data_dir()
        return
    if is_nested(target, source) or is_nested(source, target):
        _record_migration(
            "nested", source, target, warnings=[f"数据目录不能互相嵌套：{source} → {target}"]
        )
        return
    try:
        warnings, moved = _move_contents(source, target)
        write_data_dir(target)
    except OSError as error:  # 指针写不下去就留在原处，下次启动再试
        _record_migration("failed", source, target, warnings=[f"数据目录切换失败：{error}"])
        return
    clear_pending_data_dir()
    _record_migration("done", source, target, moved=moved, warnings=warnings)


def _record_migration(
    status: str, source: Path, target: Path, moved: int = 0, warnings: list[str] | None = None
) -> None:
    """记下本次搬迁的结果。``status`` 只会是 none / same / nested / done / failed。"""
    global MIGRATION
    MIGRATION = {
        "status": status,
        "moved": moved,
        "warnings": list(warnings or []),
        "source": str(source),
        "target": str(target),
    }


#: 本次启动搬迁的结构化结果，由 ``bootstrap.prepare()`` 写日志、由快照交给设置页。
MIGRATION: dict[str, Any] = {
    "status": "none",
    "moved": 0,
    "warnings": [],
    "source": "",
    "target": "",
}

_reconcile_data_dir()


DATA_DIR = read_data_dir()

APP_CONFIG_PATH = DATA_DIR / "app.json"
PROJECTS_DIR = DATA_DIR / "projects"
PROCESSORS_DIR = DATA_DIR / "processors"
RECYCLE_DIR = DATA_DIR / "recycle"

ENTRY_MAIN = PROGRAM_DIR / "main.pyw"
PYTHONW = PROGRAM_DIR / ".venv" / "Scripts" / "pythonw.exe"


# 注意：``_reconcile_data_dir()`` 必须在上面的 ``DATA_DIR = read_data_dir()``
# 之前调用，所以这些函数的顺序不能随手调整。
