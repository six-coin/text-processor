"""项目与版本链。

一个项目就是一个文件夹：

```
<数据目录>/projects/<项目 ID>/
├─ project.json     版本清单（名称、时间、每版的标题与统计）
└─ versions/
   ├─ 0001.txt      第一版：原始文本
   ├─ 0002.txt
   └─ …
```

版本号只增不减；「回到旧版本」= 截断到那一版，被丢弃的版本文件直接删除
（调用方负责让用户确认）。文件名只是序号，界面上显示的是 ``title``——
所以删掉某个处理器之后，历史里那一版的标题依然读得懂。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app import paths
from app.core import text as text_tools
from app.errors import ProjectError

SCHEMA = 1
MANIFEST = "project.json"
VERSIONS = "versions"
LEGACY_DIR = "legacy"
ORIGIN_TITLE = "原始文本"
MANUAL_TITLE = "手动修改"

#: 旧版项目里出现过的处理器名，迁移时翻成中文标题。
_LEGACY_TITLES = {
    "origin_file": ORIGIN_TITLE,
    "manual_change": MANUAL_TITLE,
    "line_strip_head_and_tail": "去除首尾空白字符",
    "line_remove_blank": "移除空行",
    "check_line_end_proc": "检查行尾标点符号",
}


@dataclass
class Version:
    index: int
    title: str
    kind: str
    at: str
    lines: int
    chars: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "kind": self.kind,
            "at": self.at,
            "lines": self.lines,
            "chars": self.chars,
        }


@dataclass
class Project:
    id: str
    name: str
    created: str
    updated: str
    folder: Path
    versions: list[Version] = field(default_factory=list)
    broken: str = ""

    @property
    def current(self) -> Version | None:
        return self.versions[-1] if self.versions else None

    def to_dict(self) -> dict[str, Any]:
        current = self.current
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "updated": self.updated,
            "count": len(self.versions),
            "lines": current.lines if current else 0,
            "broken": self.broken,
        }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _version_path(folder: Path, index: int) -> Path:
    return folder / VERSIONS / f"{index:04d}.txt"


def _read_manifest(folder: Path) -> dict[str, Any]:
    path = folder / MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProjectError("缺少项目描述文件") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectError(f"项目描述文件读不出来：{error}") from error
    if not isinstance(data, dict):
        raise ProjectError("项目描述文件的顶层必须是一个对象")
    return data


def _write_manifest(folder: Path, payload: dict[str, Any]) -> None:
    path = folder / MANIFEST
    temp = path.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    temp.replace(path)


def _build(folder: Path) -> Project:
    data = _read_manifest(folder)
    raw_versions = data.get("versions")
    if not isinstance(raw_versions, list) or not raw_versions:
        raise ProjectError("项目里没有任何版本")
    versions: list[Version] = []
    for item in raw_versions:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        versions.append(
            Version(
                index=index,
                title=str(item.get("title") or f"第 {index} 版"),
                kind=str(item.get("kind") or "processor"),
                at=str(item.get("at") or ""),
                lines=int(item.get("lines") or 0),
                chars=int(item.get("chars") or 0),
            )
        )
    versions.sort(key=lambda item: item.index)
    if not versions:
        raise ProjectError("项目里没有任何版本")
    return Project(
        id=str(data.get("id") or folder.name),
        name=str(data.get("name") or folder.name),
        created=str(data.get("created") or ""),
        updated=str(data.get("updated") or versions[-1].at),
        folder=folder,
        versions=versions,
    )


# --------------------------------------------------------------------------- 迁移


def _legacy_info(folder: Path) -> dict[str, str]:
    info: dict[str, str] = {}
    try:
        content = (folder / "project_info.txt").read_text(encoding="utf-8")
    except OSError:
        return info
    for line in content.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            info[key.strip()] = value.strip()
    return info


def _legacy_title(filename: str) -> str:
    stem = filename[:-4] if filename.endswith(".txt") else filename
    _, _, rest = stem.partition("_")
    return _LEGACY_TITLES.get(rest, rest.replace("_", " ") or ORIGIN_TITLE)


def _migrate(folder: Path) -> Project:
    """把旧版项目（project_info.txt + history/）就地转成新结构。

    旧文件不删，整体挪进 ``legacy/``——迁移出错时数据还在。
    """
    info = _legacy_info(folder)
    history = folder / "history"
    if not history.is_dir():
        raise ProjectError("缺少项目描述文件")

    files = []
    for path in history.glob("*.txt"):
        head = path.name.split("_", 1)[0]
        try:
            order = int(head)
        except ValueError:
            order = 10**6
        files.append((order, path.name, path))
    files.sort()
    if not files:
        raise ProjectError("旧项目里没有任何历史文件")

    versions_dir = folder / VERSIONS
    versions_dir.mkdir(parents=True, exist_ok=True)
    versions: list[dict[str, Any]] = []
    for _order, name, path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            logger.warning("迁移 {} 时读取失败：{}", path.name, error)
            continue
        index = len(versions) + 1
        _version_path(folder, index).write_text(content, encoding="utf-8", newline="")
        stat = text_tools.stats(content)
        try:
            at = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            at = _now()
        versions.append(
            {
                "index": index,
                "title": ORIGIN_TITLE if index == 1 else _legacy_title(name),
                "kind": "origin" if index == 1 else "processor",
                "at": at,
                "lines": stat["lines"],
                "chars": stat["chars"],
            }
        )
    if not versions:
        raise ProjectError("旧项目的历史文件都读不出来")

    created = info.get("project_creation_time") or versions[0]["at"]
    payload = {
        "schema": SCHEMA,
        "id": folder.name,
        "name": info.get("project_name") or folder.name,
        "created": created,
        "updated": info.get("project_last_modify") or versions[-1]["at"],
        "versions": versions,
    }
    _write_manifest(folder, payload)

    staging = folder / LEGACY_DIR
    staging.mkdir(exist_ok=True)
    for name in ("history", "project_info.txt", "project_log.log", "temp"):
        source = folder / name
        if not source.exists():
            continue
        target = staging / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True) if target.is_dir() else target.unlink()
        try:
            shutil.move(str(source), str(target))
        except OSError as error:
            logger.warning("迁移时无法移动 {}：{}", source, error)

    logger.info("已迁移旧项目 {}", folder.name)
    return _build(folder)


# --------------------------------------------------------------------------- 查询


def _slug(name: str) -> str:
    ascii_only = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return ascii_only[:24] or "project"


def _new_id(name: str) -> str:
    base = _slug(name)
    for salt in range(100):
        digest = hashlib.sha1(f"{name}|{_stamp()}|{salt}".encode()).hexdigest()[:4]
        candidate = f"{base}-{digest}"
        if not (paths.PROJECTS_DIR / candidate).exists():
            return candidate
    raise ProjectError("无法生成项目 ID，请换个名字")


def list_all() -> list[Project]:
    """列出所有项目，最近改动的排在前面。坏掉的项目也列出来，只是打上标记。"""
    folder = paths.PROJECTS_DIR
    if not folder.is_dir():
        return []
    projects: list[Project] = []
    for entry in folder.iterdir():
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        try:
            projects.append(_build(entry))
        except ProjectError as error:
            reason = error
            if (entry / "project_info.txt").exists():
                try:
                    projects.append(_migrate(entry))
                    continue
                except (ProjectError, OSError) as migrate_error:
                    logger.warning("迁移 {} 失败：{}", entry.name, migrate_error)
                    reason = migrate_error
            projects.append(
                Project(
                    id=entry.name,
                    name=entry.name,
                    created="",
                    updated="",
                    folder=entry,
                    versions=[],
                    broken=str(reason),
                )
            )
    projects.sort(key=lambda item: (item.updated, item.name), reverse=True)
    return projects


def load(project_id: str) -> Project:
    folder = paths.PROJECTS_DIR / project_id
    if not folder.is_dir():
        raise ProjectError("项目不存在")
    return _build(folder)


def create(name: str, initial_text: str) -> Project:
    clean = re.sub(r"[\s\u3000]+", " ", name).strip()
    if not clean:
        raise ProjectError("项目名称不能为空")
    if len(clean) > 40:
        raise ProjectError("项目名称最多 40 个字")

    folder = paths.PROJECTS_DIR / _new_id(clean)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / VERSIONS).mkdir(exist_ok=True)

    stamp = _now()
    stat = text_tools.stats(initial_text)
    _version_path(folder, 1).write_text(initial_text, encoding="utf-8", newline="")
    payload = {
        "schema": SCHEMA,
        "id": folder.name,
        "name": clean,
        "created": stamp,
        "updated": stamp,
        "versions": [
            {
                "index": 1,
                "title": ORIGIN_TITLE,
                "kind": "origin",
                "at": stamp,
                "lines": stat["lines"],
                "chars": stat["chars"],
            }
        ],
    }
    _write_manifest(folder, payload)
    logger.info("新建项目 {}（{}）", clean, folder.name)
    return _build(folder)


def remove(project: Project) -> Path:
    """移入回收站，不直接删。返回新位置。"""
    paths.RECYCLE_DIR.mkdir(parents=True, exist_ok=True)
    target = paths.RECYCLE_DIR / f"{project.id}_{_stamp()}"
    counter = 2
    while target.exists():
        target = paths.RECYCLE_DIR / f"{project.id}_{_stamp()}_{counter}"
        counter += 1
    shutil.move(str(project.folder), str(target))
    logger.info("项目 {} 已移入回收站：{}", project.id, target)
    return target


# --------------------------------------------------------------------------- 版本


def read_version(project: Project, index: int) -> str:
    path = _version_path(project.folder, index)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProjectError(f"第 {index} 版读不出来：{error}") from error


def latest_text(project: Project) -> str:
    current = project.current
    if current is None:
        return ""
    return read_version(project, current.index)


def append(project: Project, title: str, kind: str, content: str) -> Version:
    """追加一个新版本，返回它。"""
    index = (project.current.index if project.current else 0) + 1
    stat = text_tools.stats(content)
    path = _version_path(project.folder, index)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")
    version = Version(
        index=index,
        title=title or f"第 {index} 版",
        kind=kind,
        at=_now(),
        lines=stat["lines"],
        chars=stat["chars"],
    )
    data = _read_manifest(project.folder)
    data["versions"] = [
        item
        for item in data.get("versions", [])
        if isinstance(item, dict) and int(item.get("index", 0)) <= index - 1
    ]
    data["versions"].append(version.to_dict())
    data["updated"] = version.at
    data.setdefault("schema", SCHEMA)
    data["id"] = project.id
    data["name"] = project.name
    _write_manifest(project.folder, data)

    project.versions = [item for item in project.versions if item.index < index] + [version]
    project.updated = version.at
    return version


def truncate(project: Project, keep: int) -> int:
    """只保留前 ``keep`` 版，返回丢掉了几个。"""
    if keep < 1 or keep >= (project.current.index if project.current else 0):
        return 0
    dropped = [item for item in project.versions if item.index > keep]
    for item in dropped:
        try:
            _version_path(project.folder, item.index).unlink()
        except OSError as error:
            logger.warning("删除第 {} 版失败：{}", item.index, error)
    data = _read_manifest(project.folder)
    data["versions"] = [
        item
        for item in data.get("versions", [])
        if isinstance(item, dict) and int(item.get("index", 0)) <= keep
    ]
    data["updated"] = _now()
    _write_manifest(project.folder, data)
    project.versions = [item for item in project.versions if item.index <= keep]
    project.updated = str(data["updated"])
    return len(dropped)
