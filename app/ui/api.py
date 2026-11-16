"""界面与后端之间唯一的通道。

约定（前端 ``bridge.js`` 与这里一一对应）：

- 每个方法都返回**完整快照**，外加 ``ok`` 与 ``message``。前端拿到就整体重绘，
  不需要自己维护第二份状态。
- ``ok`` 为 False 表示这次操作没有生效；快照仍然完整，界面不会错位。
- 正文可能很大，只在真正变化时通过 ``text`` 字段下发；前端看到 ``text`` 才更新
  正文区域。其余字段每次都全量下发。
- 所有方法在 ``self._lock`` 内执行：pywebview 在子线程里调用 js_api，
  两次调用可能真的同时进来。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import webview
from loguru import logger

from app import i18n, paths, settings, version
from app.core import diff, processors, projects, prompt, review
from app.core import text as text_tools
from app.errors import ProcessorError, ProjectError
from app.system import shell


class Api:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._settings = settings.Settings()
        self._settings.load()
        i18n.set_language(self._settings.get("language") or i18n.initial_language())

        self._processors: list[processors.Processor] = []
        self._processor_errors: list[dict[str, str]] = []
        self._projects: list[projects.Project] = []
        self._current_id = ""
        self._preview_index = 0
        self._pending = review.Store()
        self._window: Any = None
        self._dirty = False
        self._close_confirmed = False
        self._restart = False

        self._refresh_processors()
        self._refresh_projects()
        self._restore_last()

    # ------------------------------------------------------------------ 内部

    def attach(self, window: Any) -> None:
        self._window = window

    def _refresh_processors(self) -> None:
        self._processors, self._processor_errors = processors.load_all()

    def _refresh_projects(self) -> None:
        self._projects = projects.list_all()

    def _restore_last(self) -> None:
        """恢复上次打开的项目。项目不在了就静默放弃。"""
        last = str(self._settings.get("last_project") or "")
        if not last:
            return
        if any(item.id == last and not item.broken for item in self._projects):
            self._current_id = last
            self._preview_index = 0
        else:
            self._settings.set("last_project", "")

    def _current(self) -> projects.Project | None:
        for item in self._projects:
            if item.id == self._current_id:
                return item
        return None

    def _remember_project(self, project: projects.Project | None) -> None:
        self._current_id = project.id if project else ""
        self._settings.set("last_project", self._current_id)
        try:
            self._settings.save()
        except OSError as error:  # 记不住上次项目不影响使用
            logger.warning("保存配置失败：{}", error)

    def _text_now(self) -> str:
        project = self._current()
        if project is None:
            return ""
        try:
            index = self._preview_index or (project.current.index if project.current else 1)
            return projects.read_version(project, index)
        except ProjectError as error:
            logger.warning("读取正文失败：{}", error)
            return ""

    def _snapshot(
        self,
        *,
        text: str | None = None,
        message: str = "",
        ok: bool = True,
        review_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = self._current()
        current = project.current if project else None
        payload: dict[str, Any] = {
            "ok": ok,
            "message": message,
            "language": i18n.language(),
            "languages": i18n.available(),
            "theme": self._settings.get("theme"),
            "wrap": bool(self._settings.get("wrap", True)),
            "display_limit": int(self._settings.get("display_limit", 10000)),
            "font_size": float(self._settings.get("font_size", 14.5)),
            "doc_font": str(self._settings.get("doc_font", "default")),
            "data_dir": str(paths.DATA_DIR),
            "version": version.version(),
            "projects": [item.to_dict() for item in self._projects],
            "current": None,
            "versions": [],
            "preview": None,
            "text_meta": {
                "lines": 0,
                "chars": 0,
                "shown_chars": 0,
                "shown_lines": 0,
                "truncated": False,
            },
            "processors": [
                {**item.to_dict(), "last": self._settings.recent_for(item.id)}
                for item in self._processors
            ],
            "processor_errors": self._processor_errors,
            "review": review_payload,
        }
        if project and current:
            payload["current"] = {
                "id": project.id,
                "name": project.name,
                "created": project.created,
                "updated": project.updated,
                "index": current.index,
                "title": current.title,
                "at": current.at,
            }
            payload["versions"] = [
                {**item.to_dict(), "current": item.index == current.index}
                for item in project.versions
            ]
            if self._preview_index:
                payload["preview"] = {"index": self._preview_index}
        if text is not None:
            payload["text"], payload["text_meta"] = self._shown(text)
        return payload

    def _shown(self, full: str) -> tuple[str, dict[str, Any]]:
        """按设置截断正文，同时给出全文与已显示部分的统计。

        截断只影响下发，不影响任何处理：处理器拿到的始终是完整文本。
        """
        meta: dict[str, Any] = dict(text_tools.stats(full))
        limit = int(self._settings.get("display_limit", 10000) or 0)
        shown = full[:limit] if limit and len(full) > limit else full
        meta["shown_chars"] = len(shown)
        meta["shown_lines"] = len(shown.splitlines())
        meta["truncated"] = len(shown) < len(full)
        return shown, meta

    def _fail(self, message: str, *, text: str | None = None) -> dict[str, Any]:
        return self._snapshot(text=text, message=message, ok=False)

    def _with_text(self, message: str = "", ok: bool = True) -> dict[str, Any]:
        return self._snapshot(text=self._text_now(), message=message, ok=ok)

    def _guard_editable(self) -> str:
        """能改文本的前提：有项目、且不在预览状态。返回错误文案，空表示可以。"""
        if self._current() is None:
            return i18n.t("error.no_project")
        if self._preview_index:
            return i18n.t("error.preview")
        return ""

    # ------------------------------------------------------------------ 状态

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return self._with_text()

    def get_strings(self) -> dict[str, Any]:
        with self._lock:
            return {"language": i18n.language(), "strings": i18n.table()}

    def set_language(self, code: str) -> dict[str, Any]:
        with self._lock:
            i18n.set_language(str(code))
            self._settings.set("language", i18n.language())
            try:
                self._settings.save()
            except OSError as error:
                logger.warning("保存语言失败：{}", error)
            return self._with_text()

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            patch = patch or {}
            if "theme" in patch:
                self._settings.set("theme", "dark" if patch["theme"] == "dark" else "light")
            if "wrap" in patch:
                self._settings.set("wrap", bool(patch["wrap"]))
            if "display_limit" in patch:
                self._settings.set(
                    "display_limit", settings.coerce_display_limit(patch["display_limit"])
                )
            if "font_size" in patch:
                self._settings.set("font_size", settings.coerce_font_size(patch["font_size"]))
            if "doc_font" in patch:
                self._settings.set("doc_font", settings.coerce_doc_font(patch["doc_font"]))
            try:
                self._settings.save()
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            return self._with_text()

    def reset_settings(self) -> dict[str, Any]:
        with self._lock:
            language = i18n.language()
            self._settings.set("theme", "light")
            self._settings.set("wrap", True)
            self._settings.set("language", language)
            try:
                self._settings.save()
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            return self._with_text(i18n.t("settings.reset.done"))

    def set_data_dir(self, raw: str) -> dict[str, Any]:
        """记下新的数据目录。真正的搬迁在下次启动时由 paths 完成。"""
        with self._lock:
            current = paths.DATA_DIR
            typed = str(raw or "").strip().strip('"').strip()
            if typed:
                # 用户可能只是把原路径又点了一遍，先按原样比一次。
                try:
                    if Path(typed).resolve() == current.resolve():
                        return self._snapshot(message=i18n.t("settings.data.same"), ok=False)
                except OSError:
                    pass
            try:
                target = paths.normalize_data_dir(typed, current)
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            if target == current:
                return self._snapshot(message=i18n.t("settings.data.same"), ok=False)
            if paths.is_nested(target, current) or paths.is_nested(current, target):
                return self._fail(i18n.t("settings.data.nested"))
            try:
                paths.request_data_dir(str(target))
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            snapshot = self._snapshot(message=i18n.t("settings.data.pending", path=str(target)))
            snapshot["pending_dir"] = str(target)
            return snapshot

    def restart_app(self) -> dict[str, Any]:
        """关掉窗口；真正的重启由 app.main 在释放互斥量之后完成。"""
        with self._lock:
            self._restart = True
            if self._window is not None:
                try:
                    self._window.destroy()
                except Exception as error:  # noqa: BLE001
                    logger.warning("销毁窗口失败：{}", error)
            return {"ok": True}

    def wants_restart(self) -> bool:
        return self._restart

    def browse_folder(self) -> dict[str, Any]:
        with self._lock:
            return self._pick(webview.FOLDER_DIALOG)

    def import_text(self) -> dict[str, Any]:
        """选一个文本文件读进来，给「新建项目」用。"""
        with self._lock:
            picked = self._pick(
                webview.OPEN_DIALOG,
                ("文本文件 (*.txt;*.md;*.log;*.csv)", "所有文件 (*.*)"),
            )
            if not picked.get("ok"):
                return picked
            path = Path(picked["path"])
            try:
                content = text_tools.decode_bytes(path.read_bytes())
            except OSError as error:
                return {"ok": False, "message": i18n.t("error.generic", error=error)}
            return {"ok": True, "name": path.name, "text": content, **text_tools.stats(content)}

    def _pick(self, kind: int, file_types: tuple[str, ...] | None = None) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "message": i18n.t("error.generic", error="窗口未就绪")}
        options: dict[str, Any] = {"allow_multiple": False}
        if file_types:
            options["file_types"] = file_types
        try:
            result = self._window.create_file_dialog(kind, **options)
        except Exception as error:  # noqa: BLE001
            logger.warning("打开文件对话框失败：{}", error)
            return {"ok": False, "message": i18n.t("error.generic", error=error)}
        if not result:
            return {"ok": False, "cancelled": True}
        return {"ok": True, "path": str(result[0])}

    def get_readme(self) -> dict[str, Any]:
        """当前语言的使用手册。找不到就用英文那份。"""
        with self._lock:
            for code in (i18n.language(), i18n.FALLBACK):
                path = paths.README_DIR / f"{code}.md"
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                return {"ok": True, "language": code, "markdown": text}
            return {"ok": False, "markdown": ""}

    def open_data_dir(self) -> dict[str, Any]:
        with self._lock:
            shell.open_path(str(paths.DATA_DIR))
            return self._snapshot()

    def open_recycle(self) -> dict[str, Any]:
        with self._lock:
            paths.RECYCLE_DIR.mkdir(parents=True, exist_ok=True)
            shell.open_path(str(paths.RECYCLE_DIR))
            return self._snapshot()

    def copy_text(self, text: str) -> dict[str, Any]:
        with self._lock:
            ok = shell.copy_text(str(text))
            return self._snapshot(
                message=i18n.t("common.copied") if ok else i18n.t("ai.copy.failed"), ok=ok
            )

    # ------------------------------------------------------------------ 项目

    def select_project(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            self._refresh_projects()
            target = next((item for item in self._projects if item.id == project_id), None)
            if target is None:
                return self._fail(i18n.t("error.no_current"))
            if target.broken:
                return self._fail(target.broken)
            self._preview_index = 0
            self._remember_project(target)
            return self._with_text()

    def create_project(self, name: str, initial_text: str) -> dict[str, Any]:
        with self._lock:
            try:
                project = projects.create(str(name or ""), str(initial_text or ""))
            except ProjectError as error:
                return self._fail(str(error))
            self._refresh_projects()
            self._preview_index = 0
            self._remember_project(project)
            return self._with_text(i18n.t("project.created", name=project.name))

    def delete_project(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            self._refresh_projects()
            target = next((item for item in self._projects if item.id == project_id), None)
            if target is None:
                return self._fail(i18n.t("error.no_current"))
            if target.id == self._current_id:
                return self._fail(i18n.t("project.delete.current"))
            try:
                projects.remove(target)
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            self._refresh_projects()
            return self._snapshot(message=i18n.t("project.deleted"))

    # ------------------------------------------------------------------ 版本

    def select_version(self, index: int) -> dict[str, Any]:
        with self._lock:
            project = self._current()
            if project is None or project.current is None:
                return self._fail(i18n.t("error.no_current"))
            try:
                wanted = int(index)
            except (TypeError, ValueError):
                return self._fail(i18n.t("error.generic", error="版本号不合法"))
            if wanted == project.current.index:
                self._preview_index = 0
            else:
                self._preview_index = wanted
            return self._with_text()

    def exit_preview(self) -> dict[str, Any]:
        with self._lock:
            self._preview_index = 0
            return self._with_text()

    def continue_from(self, index: int) -> dict[str, Any]:
        with self._lock:
            project = self._current()
            if project is None:
                return self._fail(i18n.t("error.no_current"))
            try:
                wanted = int(index)
            except (TypeError, ValueError):
                return self._fail(i18n.t("error.generic", error="版本号不合法"))
            try:
                projects.truncate(project, wanted)
                content = projects.read_version(project, wanted)
            except ProjectError as error:
                return self._fail(str(error))
            self._preview_index = 0
            self._refresh_projects()
            return self._snapshot(text=content, message=i18n.t("doc.continued", n=wanted))

    def save_manual(self, content: str) -> dict[str, Any]:
        with self._lock:
            blocked = self._guard_editable()
            if blocked:
                return self._fail(blocked)
            project = self._current()
            assert project is not None
            new_text = str(content or "")
            old_text = projects.latest_text(project)
            if new_text == old_text:
                return self._with_text(i18n.t("manual.unchanged"), ok=False)
            try:
                item = projects.append(project, projects.MANUAL_TITLE, "manual", new_text)
            except (OSError, ProjectError) as error:
                return self._fail(i18n.t("error.generic", error=error))
            self._refresh_projects()
            return self._snapshot(text=new_text, message=i18n.t("run.done", n=item.index))

    # ------------------------------------------------------------------ 处理器

    def apply_processor(
        self, processor_id: str, params: dict[str, Any], compare: bool = False
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._guard_editable()
            if blocked:
                return self._fail(blocked)
            project = self._current()
            assert project is not None
            processor = processors.find(self._processors, processor_id)
            if processor is None:
                return self._fail(i18n.t("error.generic", error="处理器不存在"))

            try:
                values = processors.coerce_args(processor, params)
            except ProcessorError as error:
                return self._fail(str(error))

            old_text = projects.latest_text(project)
            lines_old, trailing = text_tools.split(old_text)

            try:
                if processor.type == "check":
                    flags = processors.inspect_lines(processor, old_text, values)
                    if not flags:
                        return self._with_text(i18n.t("review.none"), ok=False)
                    items = [
                        {"index": flag["index"], "reason": flag["reason"], "text": flag["text"]}
                        for flag in flags[: diff.REVIEW_LIMIT]
                    ]
                    pending = review.Pending(
                        token="",
                        project_id=project.id,
                        title=processor.name,
                        kind="check",
                        old_text=old_text,
                        trailing=trailing,
                        items=items,
                        omitted=max(0, len(flags) - len(items)),
                    )
                else:
                    new_text = processors.apply(processor, old_text, values)
                    if new_text == old_text:
                        return self._with_text(i18n.t("run.unchanged"), ok=False)
                    lines_new, _ = text_tools.split(new_text)
                    if not compare or processor.type != "line" or len(lines_new) != len(lines_old):
                        return self._commit(project, processor, new_text, values, compare)
                    items, omitted = diff.changed_lines(lines_old, lines_new)
                    if not items:
                        return self._commit(project, processor, new_text, values, compare)
                    pending = review.Pending(
                        token="",
                        project_id=project.id,
                        title=processor.name,
                        kind="line",
                        old_text=old_text,
                        trailing=trailing,
                        new_lines=lines_new,
                        items=items,
                        omitted=omitted,
                    )
            except ProcessorError as error:
                return self._fail(i18n.t("run.failed", error=error))

            self._pending.put(pending)
            payload = {
                "token": pending.token,
                "kind": pending.kind,
                "title": pending.title,
                "count": len(pending.items) + pending.omitted,
                "omitted": pending.omitted,
                "items": pending.items,
            }
            return self._snapshot(review_payload=payload)

    def _commit(
        self,
        project: projects.Project,
        processor: processors.Processor,
        new_text: str,
        values: dict[str, Any],
        compare: bool,
    ) -> dict[str, Any]:
        try:
            item = projects.append(project, processor.name, "processor", new_text)
        except (OSError, ProjectError) as error:
            return self._fail(i18n.t("error.generic", error=error))
        self._settings.remember(processor.id, values, bool(compare))
        try:
            self._settings.save()
        except OSError as error:
            logger.warning("保存参数失败：{}", error)
        self._refresh_projects()
        return self._snapshot(text=new_text, message=i18n.t("run.done", n=item.index))

    def commit_review(self, token: str, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            pending = self._pending.get(str(token))
            if pending is None:
                return self._fail(i18n.t("error.generic", error="这次改动已经失效，请重新运行"))
            project = self._current()
            if project is None or project.id != pending.project_id:
                return self._fail(i18n.t("error.no_current"))

            chosen = {
                int(item.get("index", -1)): item
                for item in (decisions or [])
                if isinstance(item, dict) and item.get("index") is not None
            }

            if pending.kind == "line":
                old_lines, _ = text_tools.split(pending.old_text)
                final: list[str] = []
                for index, line in enumerate(pending.new_lines):
                    decision = chosen.get(index)
                    keep = decision is not None and not decision.get("apply", True)
                    final.append(old_lines[index] if keep and index < len(old_lines) else line)
                new_text = text_tools.join(final, pending.trailing)
            else:
                old_lines, _ = text_tools.split(pending.old_text)
                final = list(old_lines)
                for index, decision in chosen.items():
                    if not decision.get("apply", True):
                        continue
                    if 0 <= index < len(final):
                        edited = decision.get("text")
                        final[index] = str(edited) if edited is not None else final[index]
                new_text = text_tools.join(final, pending.trailing)

            self._pending.drop(pending.token)
            if new_text == pending.old_text:
                return self._with_text(i18n.t("manual.unchanged"), ok=False)

            try:
                item = projects.append(project, pending.title, "processor", new_text)
            except (OSError, ProjectError) as error:
                return self._fail(i18n.t("error.generic", error=error))
            self._refresh_projects()
            return self._snapshot(text=new_text, message=i18n.t("run.done", n=item.index))

    def cancel_review(self, token: str) -> dict[str, Any]:
        with self._lock:
            self._pending.drop(str(token))
            return self._with_text(i18n.t("review.cancelled"), ok=False)

    def check_processor(self, source: str) -> dict[str, Any]:
        with self._lock:
            try:
                item = processors.build(str(source or ""), "preview")
            except ProcessorError as error:
                return {"ok": False, "message": str(error)}
            return {
                "ok": True,
                "message": i18n.t("processors.valid"),
                "meta": {
                    "name": item.name,
                    "desc": item.desc,
                    "type": item.type,
                    "args": [arg.to_dict() for arg in item.args],
                },
            }

    def create_processor(self, source: str) -> dict[str, Any]:
        with self._lock:
            try:
                item = processors.create(str(source or ""))
            except ProcessorError as error:
                return self._fail(str(error))
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            self._refresh_processors()
            snapshot = self._snapshot(message=i18n.t("processors.saved"))
            snapshot["created"] = item.id
            return snapshot

    def save_processor(self, processor_id: str, source: str) -> dict[str, Any]:
        with self._lock:
            try:
                processors.save(str(processor_id), str(source or ""))
            except ProcessorError as error:
                return self._fail(str(error))
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            self._refresh_processors()
            snapshot = self._snapshot(message=i18n.t("processors.saved"))
            snapshot["saved"] = str(processor_id)
            return snapshot

    def delete_processor(self, processor_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                processors.delete(str(processor_id))
            except ProcessorError as error:
                return self._fail(str(error))
            self._refresh_processors()
            return self._snapshot(message=i18n.t("processors.deleted"))

    def restore_builtins(self) -> dict[str, Any]:
        with self._lock:
            try:
                restored = processors.restore_builtins()
            except OSError as error:
                return self._fail(i18n.t("error.generic", error=error))
            self._refresh_processors()
            message = (
                i18n.t("processors.restored", n=restored)
                if restored
                else i18n.t("processors.restored.none")
            )
            return self._snapshot(message=message, ok=bool(restored))

    def processor_template(self) -> dict[str, Any]:
        return {"source": processors.template()}

    def read_processor(self, processor_id: str) -> dict[str, Any]:
        """读一个处理器的原始源码。校验不过的文件也能读出来改。"""
        with self._lock:
            path = paths.PROCESSORS_DIR / f"{processor_id}.py"
            try:
                return {"ok": True, "source": path.read_text(encoding="utf-8")}
            except OSError as error:
                return {"ok": False, "message": i18n.t("error.generic", error=error)}

    def external_edit(self, content: str) -> dict[str, Any]:
        """把正文写到临时文件并用系统默认程序打开。"""
        with self._lock:
            path = paths.TEMP_DIR / "manual-edit.txt"
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(content or ""), encoding="utf-8", newline="")
            except OSError as error:
                return {"ok": False, "message": i18n.t("error.generic", error=error)}
            opened = shell.open_path(str(path))
            return {"ok": opened, "path": str(path)}

    def read_external(self) -> dict[str, Any]:
        """把外部编辑器改完的内容读回来。"""
        with self._lock:
            path = paths.TEMP_DIR / "manual-edit.txt"
            try:
                return {"ok": True, "text": path.read_text(encoding="utf-8")}
            except OSError as error:
                return {"ok": False, "message": i18n.t("error.generic", error=error)}

    def ai_prompt(self, request: str) -> dict[str, Any]:
        with self._lock:
            text = prompt.build(str(request or ""))
            copied = shell.copy_text(text)
            return {
                "ok": copied,
                "prompt": text,
                "message": i18n.t("ai.copied") if copied else i18n.t("ai.copy.failed"),
            }

    # ------------------------------------------------------------------ 关闭

    def set_dirty(self, flag: bool) -> dict[str, Any]:
        self._dirty = bool(flag)
        return {"ok": True}

    def allow_close(self) -> bool:
        """窗口关闭事件里调用：True 放行，False 先问一句。"""
        return self._close_confirmed or not self._dirty

    def ask_close(self) -> None:
        """在子线程里请页面弹出确认框。"""
        if self._window is None:
            return
        try:
            script = "window.TP && window.TP.hostAskClose && window.TP.hostAskClose()"
            self._window.evaluate_js(script)
        except Exception as error:  # 页面已经没了，直接放行
            logger.warning("请求关闭确认失败：{}", error)
            self._close_confirmed = True

    def answer_close(self, action: str) -> dict[str, Any]:
        if str(action) == "close":
            self._close_confirmed = True
            if self._window is not None:
                try:
                    self._window.destroy()
                except Exception as error:
                    logger.warning("销毁窗口失败：{}", error)
        return {"ok": True}
