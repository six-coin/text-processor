"""项目与版本链：新建、追加、截断、迁移、回收站。"""

from __future__ import annotations

import json

import pytest

from app import paths
from app.core import projects
from app.errors import ProjectError


def test_create_writes_origin_version():
    project = projects.create("我的项目", "第一行\n")
    assert project.name == "我的项目"
    assert len(project.versions) == 1
    assert project.versions[0].title == projects.ORIGIN_TITLE
    assert projects.latest_text(project) == "第一行\n"
    assert (project.folder / "versions" / "0001.txt").exists()


def test_append_and_read():
    project = projects.create("p", "a\n")
    version = projects.append(project, "去除首尾空白", "processor", "b\n")
    assert version.index == 2
    assert projects.latest_text(project) == "b\n"
    assert projects.read_version(project, 1) == "a\n"


def test_manifest_keeps_titles_not_ids():
    project = projects.create("p", "a")
    projects.append(project, "人看的标题", "processor", "b")
    raw = json.loads((project.folder / "project.json").read_text(encoding="utf-8"))
    assert raw["versions"][1]["title"] == "人看的标题"
    assert "processor_id" not in json.dumps(raw)


def test_truncate_drops_later_versions():
    project = projects.create("p", "a")
    projects.append(project, "x", "processor", "b")
    projects.append(project, "y", "processor", "c")
    dropped = projects.truncate(project, 2)
    assert dropped == 1
    assert len(project.versions) == 2
    assert not (project.folder / "versions" / "0003.txt").exists()


def test_list_sorted_by_update():
    first = projects.create("甲", "a")
    second = projects.create("乙", "b")
    projects.append(first, "x", "processor", "aa")
    listed = projects.list_all()
    assert listed[0].id == first.id
    assert {first.id, second.id} <= {item.id for item in listed}


def test_remove_moves_to_recycle():
    project = projects.create("p", "a")
    target = projects.remove(project)
    assert target.exists()
    assert target.parent == paths.RECYCLE_DIR
    assert not project.folder.exists()


def test_empty_name_rejected():
    with pytest.raises(ProjectError):
        projects.create("   ", "a")


def test_broken_project_is_listed_not_crashed():
    folder = paths.PROJECTS_DIR / "broken"
    folder.mkdir(parents=True)
    (folder / "project.json").write_text("{bad", encoding="utf-8")
    listed = projects.list_all()
    assert len(listed) == 1
    assert listed[0].broken


def test_legacy_project_migrates():
    folder = paths.PROJECTS_DIR / "old_one"
    (folder / "history").mkdir(parents=True)
    (folder / "project_info.txt").write_text(
        "project_id=old_one\nproject_name=旧项目\n"
        "project_creation_time=2026/03/28 20:49\nproject_last_modify=2026/03/29 10:23\n",
        encoding="utf-8",
    )
    (folder / "history" / "1_origin_file.txt").write_text("原始\n", encoding="utf-8")
    (folder / "history" / "2_line_remove_blank.txt").write_text("处理过\n", encoding="utf-8")

    listed = projects.list_all()
    assert len(listed) == 1
    project = listed[0]
    assert project.name == "旧项目"
    assert [item.title for item in project.versions] == [projects.ORIGIN_TITLE, "移除空行"]
    assert (folder / "legacy" / "project_info.txt").exists()
    assert projects.latest_text(project) == "处理过\n"


def test_stats_count_lines():
    project = projects.create("p", "a\nb\n")
    assert project.versions[0].lines == 2
    assert project.versions[0].chars == 4
