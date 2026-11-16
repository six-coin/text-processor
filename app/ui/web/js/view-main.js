/* 主视图：项目列表、正文、操作栏与历史。 */

(function (TP) {
  "use strict";

  const $ = TP.$;
  const el = TP.el;
  const esc = TP.esc;
  const T = TP.T;
  const call = TP.call;

  let projectSig = "";
  let railSig = "";
  let docSig = "";

  const TRASH_ICON =
    '<svg viewBox="0 0 24 24"><path d="M4 7h16M10 4h4M6 7l1 13h10l1-13M10 11v6M14 11v6"/></svg>';

  /* ---------------------------------------------------------------- 项目列表 */

  function renderProjects() {
    const state = TP.state;
    const container = $("#project-list");
    const query = TP.ui.projectQuery.trim().toLowerCase();
    const projects = state.projects.filter(function (item) {
      return !query || item.name.toLowerCase().indexOf(query) >= 0;
    });
    const currentId = state.current ? state.current.id : "";
    const sig = JSON.stringify([
      currentId,
      query,
      projects.map(function (item) {
        return [item.id, item.name, item.updated, item.count, item.broken];
      }),
    ]);
    const countNode = $("#project-count");
    if (countNode) {
      countNode.dataset.n = String(state.projects.length);
      countNode.textContent = T("sidebar.count", { n: state.projects.length });
    }
    if (sig === projectSig) return;
    projectSig = sig;
    container.innerHTML = "";

    if (!state.projects.length) {
      container.appendChild(
        el("div", { class: "list-empty", html: esc(T("sidebar.empty.title")) + "<br>" + esc(T("sidebar.empty.desc")) })
      );
      return;
    }
    if (!projects.length) {
      container.appendChild(el("div", { class: "list-empty", text: T("sidebar.no_match") }));
      return;
    }

    const fragment = document.createDocumentFragment();
    projects.forEach(function (item) {
      const row = el("div", {
        class:
          "list-row" + (item.id === currentId ? " is-active" : "") + (item.broken ? " is-broken" : ""),
        tabindex: "0",
        dataset: { id: item.id },
      });
      const body = el("div", { class: "row-body" });
      body.appendChild(el("span", { class: "row-title", text: item.name }));
      const sub = item.broken
        ? T("sidebar.broken")
        : (item.count ? item.count + " 版" : "0 版") + (item.updated ? " · " + TP.shortTime(item.updated) : "");
      body.appendChild(el("span", { class: "row-sub", text: sub }));
      row.appendChild(body);

      const remove = el("button", { class: "icon-btn row-action danger", type: "button", title: T("common.delete") });
      remove.innerHTML = TRASH_ICON;
      remove.addEventListener("click", function (event) {
        event.stopPropagation();
        askDelete(item);
      });
      row.appendChild(remove);

      row.addEventListener("click", function () {
        if (item.broken) {
          TP.toast(item.broken, true);
          return;
        }
        if (item.id === currentId) return;
        call("select_project", item.id).then(function (snapshot) {
          if (snapshot) TP.apply(snapshot);
        });
      });
      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          row.click();
        }
      });
      fragment.appendChild(row);
    });
    container.appendChild(fragment);
  }

  function askDelete(item) {
    TP.confirm({
      title: T("project.delete.title"),
      text: T("project.delete.text", { name: item.name }),
      ok: T("common.delete"),
      danger: true,
    }).then(function (ok) {
      if (!ok) return;
      call("delete_project", item.id).then(function (snapshot) {
        if (snapshot) TP.apply(snapshot);
      });
    });
  }

  /* ---------------------------------------------------------------- 正文 */

  function emptyArt() {
    return (
      '<svg viewBox="0 0 96 96"><path d="M26 12h30l18 18v54a4 4 0 0 1-4 4H26a4 4 0 0 1-4-4V16a4 4 0 0 1 4-4Z"/>' +
      '<path d="M56 12v18h18M34 46h28M34 58h28M34 70h18"/></svg>'
    );
  }

  function renderDoc() {
    const state = TP.state;
    const current = state.current;
    const titleNode = $("#doc-title");
    const metaNode = $("#doc-meta");
    const empty = $("#doc-empty");
    const textNode = $("#doc-text");
    const gutter = $("#gutter");
    const body = $("#doc-body");

    if (!current) {
      titleNode.textContent = T("doc.empty.title");
      metaNode.innerHTML = "";
      empty.classList.remove("hidden");
      empty.innerHTML =
        '<div class="empty">' +
        emptyArt() +
        "<h3>" + esc(T("doc.empty.title")) + "</h3>" +
        "<p>" + esc(T("doc.empty.desc")) + "</p>" +
        '<div class="empty-actions"><button class="btn primary" data-act="new">' +
        esc(T("sidebar.new")) +
        "</button></div></div>";
      textNode.classList.add("hidden");
      gutter.classList.add("hidden");
      $("#btn-manual").disabled = true;
      $("#btn-find").disabled = true;
      $("#preview-banner").classList.add("hidden");
      docSig = "";
      return;
    }

    empty.classList.add("hidden");
    textNode.classList.remove("hidden");
    $("#btn-manual").disabled = TP.inPreview();
    $("#btn-find").disabled = false;

    const viewing = state.preview ? state.preview.index : null;
    const shown = viewing
      ? state.versions.find(function (item) { return item.index === viewing; })
      : null;

    titleNode.textContent = current.name;

    const parts = [];
    parts.push(
      '<span class="chip" id="doc-version"' + (viewing ? ' data-kind="preview"' : "") + ">" +
        esc(T("doc.version", { n: viewing || current.index })) +
        "</span>"
    );
    parts.push('<span class="meta-text">' + esc((shown || current).title) + "</span>");
    parts.push('<span class="meta-text">' + esc(TP.shortTime((shown || current).at)) + "</span>");
    parts.push(
      '<span class="meta-text">' +
        esc(T("doc.meta", { lines: TP.number(state.text_meta.lines), chars: TP.number(state.text_meta.chars) })) +
        "</span>"
    );
    metaNode.innerHTML = parts.join("");

    renderPreviewBanner();

    // 只有「真的多了一版」才脉冲；切到旧版本预览、退出预览都不算。
    if (TP.ui.lastBaseIndex && current.index > TP.ui.lastBaseIndex) {
      TP.replay($("#doc-version"), "is-flash", 1000);
    }
    TP.ui.lastBaseIndex = current.index;

    const wrap = !!state.wrap;
    body.classList.toggle("is-nowrap", !wrap);
    gutter.classList.toggle("hidden", wrap);
    $("#btn-wrap").classList.toggle("is-on", !wrap);
    $("#btn-wrap").title = T(wrap ? "doc.wrap.on" : "doc.wrap.off");

    const key =
      current.id + "#" + (viewing || current.index) + "|" + (TP.ui.find.open ? TP.ui.find.query : "");
    if (key !== docSig) {
      docSig = key;
      paintText();
      TP.replay(textNode, "is-entering", 240);
      textNode.scrollTop = 0;
      gutter.scrollTop = 0;
    }
    paintGutter();
  }

  let gutterSig = "";

  function paintGutter() {
    const state = TP.state;
    const gutterText = $("#gutter-text");
    if (state.wrap) {
      gutterSig = "";
      return;
    }
    const lines = (state.text_meta && state.text_meta.lines) || 0;
    const sig = lines + "|" + ((state.text || "").length);
    if (sig === gutterSig && gutterText.textContent) return;
    gutterSig = sig;
    let numbers = "";
    for (let index = 1; index <= lines; index += 1) numbers += index + "\n";
    gutterText.textContent = numbers;
  }

  function paintText() {
    const state = TP.state;
    const text = state.text == null ? "" : state.text;
    const textNode = $("#doc-text");
    const find = TP.ui.find;

    if (find.open && find.query) {
      textNode.innerHTML = highlight(text, find.query);
      const total = textNode.querySelectorAll("mark").length;
      find.hits = total;
      if (find.index >= total) find.index = 0;
      paintFindCount();
      paintActiveHit();
    } else {
      textNode.textContent = text;
      find.hits = 0;
      paintFindCount();
    }
  }

  function highlight(text, query) {
    const needle = String(query || "");
    if (!needle) return esc(text);
    const lower = text.toLowerCase();
    const target = needle.toLowerCase();
    let out = "";
    let from = 0;
    let count = 0;
    while (count < 2000) {
      const at = lower.indexOf(target, from);
      if (at < 0) break;
      out += esc(text.slice(from, at));
      out += '<mark data-hit="' + count + '">' + esc(text.slice(at, at + target.length)) + "</mark>";
      count += 1;
      from = at + target.length;
    }
    out += esc(text.slice(from));
    return out;
  }

  function paintFindCount() {
    const node = $("#find-count");
    const find = TP.ui.find;
    if (!find.open || !find.query) {
      node.textContent = "";
      return;
    }
    if (!find.hits) {
      node.textContent = T("doc.find.none");
      return;
    }
    node.textContent = T("doc.find.count", { n: find.index + 1, total: find.hits });
  }

  function paintActiveHit() {
    const node = $("#doc-text");
    const marks = node.querySelectorAll("mark");
    marks.forEach(function (mark) {
      mark.classList.remove("is-active");
    });
    const find = TP.ui.find;
    if (!marks.length) return;
    const active = marks[Math.min(find.index, marks.length - 1)];
    if (active) {
      active.classList.add("is-active");
      active.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  function renderPreviewBanner() {
    const state = TP.state;
    const banner = $("#preview-banner");
    if (!state.preview) {
      banner.classList.add("hidden");
      return;
    }
    const version = state.versions.find(function (item) {
      return item.index === state.preview.index;
    });
    $("#preview-text").textContent = T("doc.preview", {
      n: state.preview.index,
      title: version ? version.title : "",
    });
    banner.classList.remove("hidden");
    $("#preview-continue").disabled = state.preview.index >= (state.current ? state.current.index : 0);
  }

  /* ---------------------------------------------------------------- 操作栏 */

  function renderRail() {
    const state = TP.state;
    const ops = $("#rail-ops");
    const history = $("#rail-history");
    const current = state.current;

    const sig = JSON.stringify([
      current ? current.id : "",
      state.versions.map(function (item) { return [item.index, item.title, item.current]; }),
      state.preview ? state.preview.index : 0,
      state.processors.map(function (item) { return [item.id, item.name, item.desc, item.type]; }),
    ]);
    if (sig === railSig) return;
    railSig = sig;

    /* 操作 */
    ops.innerHTML = "";
    const manual = el("button", { class: "btn block rail-manual", type: "button" });
    manual.innerHTML = "<span>" + esc(T("rail.manual")) + "</span>";
    manual.disabled = !current || TP.inPreview();
    manual.addEventListener("click", function () {
      TP.manualEdit();
    });
    ops.appendChild(manual);

    const groups = [
      { type: "line", items: [] },
      { type: "file", items: [] },
      { type: "check", items: [] },
    ];
    state.processors.forEach(function (item) {
      const group = groups.find(function (entry) {
        return entry.type === item.type;
      });
      if (group) group.items.push(item);
    });

    const available = groups.filter(function (group) {
      return group.items.length;
    });

    if (!available.length) {
      ops.appendChild(el("div", { class: "list-empty", text: T("rail.ops.empty") }));
    }

    available.forEach(function (group) {
      const box = el("div", { class: "rail-group" });
      const head = el("div", { class: "rail-group-head" });
      head.appendChild(el("span", { text: T("type." + group.type) }));
      head.appendChild(el("span", { class: "count", text: String(group.items.length) }));
      box.appendChild(head);
      group.items.forEach(function (item) {
        const row = el("button", { class: "rail-row", type: "button" });
        row.innerHTML =
          '<span class="dot" data-type="' + item.type + '"></span>' +
          '<span class="row-body"><span class="row-name">' + esc(item.name) + "</span>" +
          '<span class="row-desc">' + esc(item.desc) + "</span></span>";
        row.addEventListener("click", function () {
          if (!current) {
            TP.toast(T("error.no_project"), true);
            return;
          }
          if (TP.inPreview()) {
            TP.toast(T("error.preview"), true);
            return;
          }
          TP.runProcessor(item);
        });
        box.appendChild(row);
      });
      ops.appendChild(box);
    });

    /* 历史 */
    history.innerHTML = "";
    if (!current || !state.versions.length) {
      history.appendChild(el("div", { class: "list-empty", text: T("rail.history.empty") }));
      return;
    }
    const hint = el("div", { class: "rail-group-head", text: T("rail.history.hint") });
    history.appendChild(hint);
    state.versions
      .slice()
      .reverse()
      .forEach(function (item) {
        const viewing = state.preview && state.preview.index === item.index;
        const row = el("button", {
          class:
            "hist-row" + (item.current ? " is-current" : "") + (viewing ? " is-viewing" : ""),
          type: "button",
        });
        row.innerHTML =
          '<span class="hist-index">' + item.index + "</span>" +
          '<span><span class="hist-title">' + esc(item.title) + "</span>" +
          '<span class="hist-sub">' + esc(TP.shortTime(item.at)) + " · " +
          TP.number(item.lines) + " 行</span></span>" +
          (item.current ? '<span class="hist-flag">' + esc(T("rail.history.current")) + "</span>" : "");
        row.addEventListener("click", function () {
          if (item.current && !state.preview) return;
          call("select_version", item.index).then(function (snapshot) {
            if (snapshot) TP.apply(snapshot);
          });
        });
        history.appendChild(row);
      });

    TP.replay(ops, "is-entering", 240);

    // 新版本多出来时，让最新一条闪一下，避免「点了没反应」的错觉。
    const count = state.versions.length;
    if (TP.ui.lastVersionCount && count > TP.ui.lastVersionCount) {
      const first = history.querySelector(".hist-row");
      if (first) TP.replay(first, "is-flash", 1000);
    }
    TP.ui.lastVersionCount = count;
  }

  /* ---------------------------------------------------------------- 操作栏页签 */

  function setRailTab(tab) {
    if (TP.ui.railTab === tab) return;
    TP.ui.railTab = tab;
    TP.$$("#rail-tabs .seg-item").forEach(function (item) {
      item.classList.toggle("is-active", item.dataset.tab === tab);
    });
    const ops = $("#rail-ops");
    const history = $("#rail-history");
    const showOps = tab === "ops";
    ops.classList.toggle("hidden", !showOps);
    history.classList.toggle("hidden", showOps);
    TP.replay(showOps ? ops : history, "is-entering", 240);
  }

  /* ---------------------------------------------------------------- 查找 */

  function setFindOpen(open) {
    const bar = $("#findbar");
    TP.ui.find.open = open;
    bar.classList.toggle("hidden", !open);
    if (open) {
      const input = $("#find-input");
      input.focus();
      input.select();
      if (input.value) {
        TP.ui.find.query = input.value;
        paintText();
      }
    } else {
      TP.ui.find.query = "";
      TP.ui.find.index = 0;
      paintText();
    }
  }

  function findStep(delta) {
    const find = TP.ui.find;
    if (!find.hits) return;
    find.index = (find.index + delta + find.hits) % find.hits;
    paintFindCount();
    paintActiveHit();
  }

  /* ---------------------------------------------------------------- 绑定 */

  function bind() {
    $("#btn-new-project").addEventListener("click", function () {
      TP.newProject();
    });

    const search = $("#project-search");
    search.addEventListener(
      "input",
      TP.debounce(function () {
        TP.ui.projectQuery = search.value;
        $("#search-clear").classList.toggle("hidden", !search.value);
        projectSig = "";
        renderProjects();
      }, 120)
    );
    $("#search-clear").addEventListener("click", function () {
      search.value = "";
      TP.ui.projectQuery = "";
      $("#search-clear").classList.add("hidden");
      projectSig = "";
      renderProjects();
      search.focus();
    });

    $("#btn-manual").addEventListener("click", function () {
      TP.manualEdit();
    });

    $("#btn-wrap").addEventListener("click", function () {
      const next = !TP.state.wrap;
      call("update_settings", { wrap: next }).then(function (snapshot) {
        if (snapshot) TP.apply(snapshot);
      });
    });

    $("#btn-find").addEventListener("click", function () {
      setFindOpen(!TP.ui.find.open);
    });
    $("#find-close").addEventListener("click", function () {
      setFindOpen(false);
    });
    $("#find-prev").addEventListener("click", function () {
      findStep(-1);
    });
    $("#find-next").addEventListener("click", function () {
      findStep(1);
    });
    $("#find-input").addEventListener(
      "input",
      TP.debounce(function () {
        TP.ui.find.query = $("#find-input").value;
        TP.ui.find.index = 0;
        paintText();
        if (TP.ui.find.hits) paintActiveHit();
      }, 180)
    );
    $("#find-input").addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        findStep(event.shiftKey ? -1 : 1);
      }
    });

    $("#preview-exit").addEventListener("click", function () {
      call("exit_preview").then(function (snapshot) {
        if (snapshot) TP.apply(snapshot);
      });
    });

    $("#preview-continue").addEventListener("click", function () {
      const state = TP.state;
      if (!state.preview || !state.current) return;
      const index = state.preview.index;
      const count = state.current.index - index;
      if (count <= 0) {
        TP.toast(T("doc.preview.nothing"));
        return;
      }
      TP.confirm({
        title: T("doc.preview.confirm.title", { n: index }),
        text: T("doc.preview.confirm.text", { n: index, count: count }),
        ok: T("doc.preview.confirm.ok"),
        danger: true,
      }).then(function (ok) {
        if (!ok) return;
        call("continue_from", index).then(function (snapshot) {
          if (snapshot) TP.apply(snapshot);
        });
      });
    });

    $("#rail-tabs").addEventListener("click", function (event) {
      const button = event.target.closest(".seg-item");
      if (!button) return;
      setRailTab(button.dataset.tab);
    });

    $("#btn-processors").addEventListener("click", function () {
      TP.openProcessors();
    });

    $("#doc-empty").addEventListener("click", function (event) {
      if (event.target.closest('[data-act="new"]')) TP.newProject();
    });

    $("#doc-text").addEventListener("scroll", function () {
      const gutter = $("#gutter");
      if (!gutter.classList.contains("hidden")) gutter.scrollTop = this.scrollTop;
    });

    // 窄屏下操作栏是抽屉，点遮罩关掉。
    $("#rail-scrim").addEventListener("click", function () {
      $("#app").classList.remove("rail-open");
    });
    $("#btn-rail").addEventListener("click", function () {
      $("#app").classList.toggle("rail-open");
    });
  }

  TP.renderProjects = renderProjects;
  TP.renderDoc = renderDoc;
  TP.renderRail = renderRail;
  TP.setRailTab = setRailTab;
  TP.setFindOpen = setFindOpen;
  TP.bindMain = bind;
})(window.TP);
