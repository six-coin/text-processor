/* 处理器页：列表 + 代码编辑器。 */

(function (TP) {
  "use strict";

  const $ = TP.$;
  const el = TP.el;
  const esc = TP.esc;
  const T = TP.T;
  const call = TP.call;

  let listSig = "";
  let editorKey = "";

  const GROUP_ORDER = ["line", "file", "check"];

  /* ---------------------------------------------------------------- 列表 */

  function renderList() {
    const state = TP.state;
    const container = $("#proc-list");
    const broken = state.processor_errors || [];
    const sig = JSON.stringify([
      TP.ui.processorId,
      state.processors.map(function (item) {
        return [item.id, item.name, item.desc, item.type, item.builtin];
      }),
      broken,
    ]);
    if (sig === listSig) return;
    listSig = sig;
    container.innerHTML = "";

    const groups = GROUP_ORDER.map(function (type) {
      return {
        type: type,
        items: state.processors.filter(function (item) {
          return item.type === type;
        }),
      };
    }).filter(function (group) {
      return group.items.length;
    });

    groups.forEach(function (group) {
      const head = el("div", { class: "rail-group-head", style: "padding:8px 9px 4px" });
      head.appendChild(el("span", { text: T("type." + group.type) }));
      head.appendChild(el("span", { class: "count", text: String(group.items.length) }));
      container.appendChild(head);

      group.items.forEach(function (item) {
        const row = el("button", {
          class: "proc-row" + (item.id === TP.ui.processorId ? " is-active" : ""),
          type: "button",
        });
        row.innerHTML =
          '<span class="dot" data-type="' + item.type + '"></span>' +
          '<span class="row-body"><span class="row-name">' + esc(item.name) +
          (item.builtin ? '<span class="proc-badge">' + esc(T("processors.builtin")) + "</span>" : "") +
          "</span>" +
          '<span class="row-desc">' + esc(item.desc) + "</span></span>";
        row.addEventListener("click", function () {
          selectProcessor(item.id);
        });
        container.appendChild(row);
      });
    });

    if (broken.length) {
      const head = el("div", { class: "rail-group-head", style: "padding:12px 9px 4px" });
      head.appendChild(el("span", { text: T("processors.broken") }));
      container.appendChild(head);
      broken.forEach(function (item) {
        const id = item.file.replace(/\.py$/, "");
        const row = el("button", {
          class: "proc-row is-broken" + (id === TP.ui.processorId ? " is-active" : ""),
          type: "button",
        });
        row.innerHTML =
          '<span class="dot" style="background:var(--red)"></span>' +
          '<span class="row-body"><span class="row-name">' + esc(id) +
          '<span class="proc-badge">' + esc(T("processors.broken")) + "</span></span>" +
          '<span class="row-desc">' + esc(item.error) + "</span></span>";
        row.addEventListener("click", function () {
          selectProcessor(id);
        });
        container.appendChild(row);
      });
    }

    if (!groups.length && !broken.length) {
      container.appendChild(
        el("div", { class: "list-empty", text: T("processors.empty.title") })
      );
    }
  }

  /* ---------------------------------------------------------------- 选择 */

  function selectProcessor(id) {
    if (TP.ui.draft && TP.ui.dirty) {
      TP.confirm({
        title: T("processors.title"),
        text: T("processors.confirm.leave"),
        ok: T("common.confirm"),
        danger: true,
      }).then(function (ok) {
        if (!ok) return;
        applySelection(id);
      });
      return;
    }
    applySelection(id);
  }

  function applySelection(id) {
    TP.ui.processorId = id;
    TP.ui.draft = null;
    TP.ui.dirty = false;
    TP.call("set_dirty", false);
    editorKey = "";
    renderList();
    renderEditor();

    const broken = (TP.state.processor_errors || []).some(function (item) {
      return item.file.replace(/\.py$/, "") === id;
    });
    if (!broken) return;
    call("read_processor", id).then(function (result) {
      if (!result || !result.ok) return;
      TP.ui.draft = { source: result.source || "", isNew: false, token: "broken" + Date.now() };
      editorKey = "";
      renderList();
      renderEditor(true);
    });
  }

  /* ---------------------------------------------------------------- 编辑器 */

  function currentSource() {
    if (TP.ui.draft) return TP.ui.draft.source;
    const item = TP.processorById(TP.ui.processorId);
    return item ? item.source : "";
  }

  function renderEditor(force) {
    const main = $("#proc-main");
    const draft = TP.ui.draft;
    const processor = TP.processorById(TP.ui.processorId);
    const brokenError = (TP.state.processor_errors || []).find(function (item) {
      return item.file.replace(/\.py$/, "") === TP.ui.processorId;
    });

    if (!draft && !processor && !brokenError) {
      if (editorKey === "empty") return;
      editorKey = "empty";
      const hasAny = TP.state.processors.length > 0;
      main.innerHTML =
        '<div class="empty" style="grid-row:1/-1">' +
        '<svg viewBox="0 0 96 96"><path d="M30 20h26l14 14v42a4 4 0 0 1-4 4H30a4 4 0 0 1-4-4V24a4 4 0 0 1 4-4Z"/>' +
        '<path d="M56 20v14h14M36 52l8 8 16-16"/></svg>' +
        "<h3>" + esc(T(hasAny ? "processors.pick.title" : "processors.empty.title")) + "</h3>" +
        "<p>" + esc(T(hasAny ? "processors.pick.desc" : "processors.empty.desc")) + "</p>" +
        '<div class="empty-actions">' +
        '<button class="btn" data-act="manual">' + esc(T("processors.new.manual")) + "</button>" +
        '<button class="btn primary" data-act="ai">' + esc(T("processors.new.ai")) + "</button>" +
        "</div></div>";
      main.querySelector('[data-act="manual"]').addEventListener("click", startManual);
      main.querySelector('[data-act="ai"]').addEventListener("click", function () {
        TP.aiWizard();
      });
      return;
    }

    const key =
      (draft ? "draft:" + draft.token : "id:" + TP.ui.processorId) +
      "|" +
      (draft ? "" : processor ? String(processor.source.length) : "broken");
    if (!force && key === editorKey) return;
    editorKey = key;

    const source = draft ? draft.source : processor ? processor.source : "";
    const name = draft
      ? draft.isNew
        ? T("processors.new.manual")
        : TP.ui.processorId
      : processor
        ? processor.name
        : TP.ui.processorId;
    const desc = processor ? processor.desc : brokenError ? brokenError.error : "";

    main.innerHTML = "";

    const head = el("div", { class: "editor-head" });
    const titles = el("div", { class: "editor-titles" });
    const titleRow = el("h3");
    titleRow.textContent = name;
    titles.appendChild(titleRow);
    const meta = el("p");
    const bits = [];
    if (processor) {
      bits.push(T("type." + processor.type));
      bits.push(processor.args.length ? T("processors.arg_count", { n: processor.args.length }) : T("processors.no_args"));
      if (processor.builtin) bits.push(T("processors.builtin"));
    }
    if (desc) bits.push(desc);
    meta.textContent = bits.join(" · ");
    titles.appendChild(meta);

    const tools = el("div", { class: "editor-tools" });
    const checkBtn = el("button", { class: "btn", type: "button", text: T("processors.validate") });
    const saveBtn = el("button", { class: "btn primary", type: "button", text: T("processors.save") });
    const delBtn = el("button", { class: "btn danger-ghost", type: "button", text: T("processors.delete") });
    tools.appendChild(checkBtn);
    if (processor || brokenError) tools.appendChild(delBtn);
    tools.appendChild(saveBtn);

    head.appendChild(titles);
    head.appendChild(tools);
    main.appendChild(head);

    const box = el("div", { class: "editor-box" });
    const gutterBox = el("div", { class: "editor-gutter" });
    const gutterPre = el("pre");
    gutterBox.appendChild(gutterPre);
    const areaBox = el("div", { class: "editor-area" });
    const area = el("textarea", { spellcheck: "false", placeholder: T("processors.editor.placeholder") });
    area.value = source;
    areaBox.appendChild(area);
    box.appendChild(gutterBox);
    box.appendChild(areaBox);
    main.appendChild(box);

    const status = el("div", { class: "editor-status" });
    const statusText = el("span", { class: "mono" });
    const dirtyFlag = el("span", { class: "chip plain hidden", text: T("processors.unsaved") });
    status.appendChild(statusText);
    status.appendChild(dirtyFlag);
    main.appendChild(status);

    function paintGutter() {
      const count = area.value.split("\n").length;
      let out = "";
      for (let index = 1; index <= count; index += 1) out += index + "\n";
      gutterPre.textContent = out;
    }

    function paintStatus(kind, message) {
      statusText.textContent = message || "";
      statusText.className = "mono" + (kind ? " " + kind : "");
    }

    let lastDirty = false;

    function markDirty() {
      if (TP.ui.draft) TP.ui.draft.source = area.value;
      const changed = area.value !== source;
      if (changed === lastDirty) return;
      lastDirty = changed;
      dirtyFlag.classList.toggle("hidden", !changed);
      TP.ui.dirty = changed;
      TP.call("set_dirty", changed);
    }

    const paintGutterSoon = TP.debounce(paintGutter, 120);

    paintGutter();
    if (brokenError) paintStatus("bad", brokenError.error);
    else paintStatus("", "");

    area.addEventListener("input", function () {
      paintGutterSoon();
      markDirty();
    });
    area.addEventListener("scroll", function () {
      gutterBox.scrollTop = area.scrollTop;
    });
    area.addEventListener("keydown", function (event) {
      if (event.key === "Tab") {
        event.preventDefault();
        const start = area.selectionStart;
        const end = area.selectionEnd;
        area.value = area.value.slice(0, start) + "    " + area.value.slice(end);
        area.selectionStart = area.selectionEnd = start + 4;
        paintGutter();
        markDirty();
      }
    });

    function doCheck() {
      call("check_processor", area.value).then(function (result) {
        if (!result) return;
        if (result.ok) {
          paintStatus("ok", T("processors.valid") + " · " + result.meta.name + " · " + T("type." + result.meta.type));
        } else {
          paintStatus("bad", result.message);
        }
      });
    }

    function doSave() {
      const source2 = area.value;
      if (!source2.trim()) {
        paintStatus("bad", T("processors.need_code"));
        return;
      }
      const isNew = !!(TP.ui.draft && TP.ui.draft.isNew);
      const method = isNew ? "create_processor" : "save_processor";
      const args = isNew ? [source2] : [TP.ui.processorId, source2];
      saveBtn.disabled = true;
      call.apply(null, [method].concat(args)).then(function (snapshot) {
        saveBtn.disabled = false;
        if (!snapshot) return;
        const target = snapshot.created || snapshot.saved || TP.ui.processorId;
        TP.ui.draft = null;
        TP.ui.dirty = false;
        TP.call("set_dirty", false);
        TP.apply(snapshot);
        if (target) {
          TP.ui.processorId = target;
          editorKey = "";
          renderList();
          renderEditor(true);
        }
      });
    }

    checkBtn.addEventListener("click", doCheck);
    saveBtn.addEventListener("click", doSave);
    area.addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        doSave();
      }
    });

    if (processor || brokenError) {
      delBtn.addEventListener("click", function () {
        TP.confirm({
          title: T("processors.delete.title"),
          text: T("processors.delete.text", { name: name }),
          ok: T("common.delete"),
          danger: true,
        }).then(function (ok) {
          if (!ok) return;
          call("delete_processor", TP.ui.processorId).then(function (snapshot) {
            if (!snapshot) return;
            TP.ui.processorId = "";
            TP.ui.draft = null;
            TP.ui.dirty = false;
            TP.call("set_dirty", false);
            editorKey = "";
            TP.apply(snapshot);
            renderList();
            renderEditor(true);
          });
        });
      });
    }

    TP.replay(main, "is-entering", 240);

    setTimeout(function () {
      area.focus();
    }, 40);
  }

  /* ---------------------------------------------------------------- 新建 */

  function startManual() {
    call("processor_template").then(function (result) {
      TP.ui.processorId = "";
      TP.ui.draft = {
        source: (result && result.source) || "",
        isNew: true,
        token: String(Date.now()),
      };
      TP.ui.dirty = false;
      editorKey = "";
      renderList();
      renderEditor(true);
    });
  }

  function openPage() {
    TP.switchView("processors");
    if (TP.ui.processorId && !TP.processorById(TP.ui.processorId)) TP.ui.processorId = "";
    editorKey = "";
    listSig = "";
    renderList();
    renderEditor(true);
  }

  /* ---------------------------------------------------------------- 绑定 */

  function bind() {
    $("#proc-back").addEventListener("click", function () {
      if (TP.ui.dirty) {
        TP.confirm({
          title: T("processors.title"),
          text: T("processors.confirm.leave"),
          ok: T("common.confirm"),
          danger: true,
        }).then(function (ok) {
          if (!ok) return;
          TP.ui.dirty = false;
          TP.call("set_dirty", false);
          TP.switchView("main");
        });
        return;
      }
      TP.switchView("main");
    });

    $("#proc-new-manual").addEventListener("click", startManual);
    $("#proc-new-ai").addEventListener("click", function () {
      TP.aiWizard();
    });

    $("#proc-restore").addEventListener("click", function () {
      call("restore_builtins").then(function (snapshot) {
        if (snapshot) TP.apply(snapshot);
      });
    });
  }

  TP.openProcessors = openPage;
  TP.renderProcessors = function () {
    renderList();
    renderEditor(false);
  };
  TP.bindProcessors = bind;
})(window.TP);
