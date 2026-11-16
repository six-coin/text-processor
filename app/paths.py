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
import tempfile
from pathlib import Path

VENDOR = "six-coin"
PROJECT = "text-processor"

PACKAGE_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = PACKAGE_DIR.parent
WEB_DIR = PACKAGE_DIR / "ui" / "web"
RESOURCE_DIR = PACKAGE_DIR / "resources"
BUILTIN_PROCESSORS_DIR = RESOURCE_DIR / "processors"
LOCALES_DIR = PACKAGE_DIR / "locales"

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
    if target == read_data_dir():
        clear_pending_data_dir()
        return target
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


def is_nested(inner: Path, outer: Path) -> bool:
    """``inner`` 是否在 ``outer`` 里（含相等）。"""
    try:
        inner.relative_to(outer)
    except ValueError:
        return False
    return True


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
            shutil.move(str(item), str(destination))
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
    global MIGRATION_WARNINGS, MIGRATED_ITEMS
    if os.environ.get(_ENV_DATA, "").strip():
        return
    source = read_data_dir()
    target = pending_data_dir() or normalize_data_dir(str(source))
    if target == source:
        clear_pending_data_dir()
        return
    if is_nested(target, source) or is_nested(source, target):
        MIGRATION_WARNINGS = [f"数据目录不能互相嵌套：{source} → {target}"]
        return
    MIGRATION_WARNINGS, MIGRATED_ITEMS = _move_contents(source, target)
    write_data_dir(target)
    clear_pending_data_dir()


#: 启动时搬迁数据的警告与条数，由 ``bootstrap.prepare()`` 取走写日志。
MIGRATION_WARNINGS: list[str] = []
MIGRATED_ITEMS = 0

_reconcile_data_dir()


DATA_DIR = read_data_dir()

APP_CONFIG_PATH = DATA_DIR / "app.json"
PROJECTS_DIR = DATA_DIR / "projects"
PROCESSORS_DIR = DATA_DIR / "processors"
RECYCLE_DIR = DATA_DIR / "_recycle"

ENTRY_MAIN = PROGRAM_DIR / "main.pyw"
PYTHONW = PROGRAM_DIR / ".venv" / "Scripts" / "pythonw.exe"


# 注意：``_reconcile_data_dir()`` 必须在上面的 ``DATA_DIR = read_data_dir()``
# 之前调用，所以这些函数的顺序不能随手调整。
