/* 设置页：常规、外观、数据、关于。 */

(function (TP) {
  "use strict";

  const $ = TP.$;
  const el = TP.el;
  const esc = TP.esc;
  const T = TP.T;
  const call = TP.call;

  const SECTIONS = [
    { id: "general", label: "settings.general" },
    { id: "appearance", label: "settings.appearance" },
    { id: "data", label: "settings.data" },
    { id: "about", label: "settings.about" },
  ];

  let navSig = "";
  let bodySig = "";

  function renderNav() {
    const nav = $("#settings-nav");
    const sig = TP.ui.settingsTab + "|" + TP.state.language;
    if (sig === navSig) return;
    navSig = sig;
    nav.innerHTML = "";
    SECTIONS.forEach(function (section) {
      const item = el("button", {
        class: "settings-nav-item" + (TP.ui.settingsTab === section.id ? " is-active" : ""),
        type: "button",
        text: T(section.label),
      });
      item.addEventListener("click", function () {
        if (TP.ui.settingsTab === section.id) return;
        TP.ui.settingsTab = section.id;
        bodySig = "";
        renderNav();
        renderBody();
        const body = $("#settings-content");
        if (body) TP.replay(body, "is-entering", 240);
      });
      nav.appendChild(item);
    });
  }

  function row(label, hint, control) {
    const node = el("div", { class: "card-row" });
    const box = el("div", { class: "row-label" });
    box.appendChild(el("strong", { text: label }));
    if (hint) box.appendChild(el("span", { text: hint }));
    node.appendChild(box);
    const holder = el("div", { class: "row-control" });
    if (control) holder.appendChild(control);
    node.appendChild(holder);
    return node;
  }

  function card(rows) {
    const node = el("div", { class: "card" });
    rows.forEach(function (item) {
      node.appendChild(item);
    });
    return node;
  }

  function renderBody() {
    const body = $("#settings-content");
    const state = TP.state;
    const sig = JSON.stringify([
      TP.ui.settingsTab,
      state.language,
      state.theme,
      state.wrap,
      state.data_dir,
      state.version,
      (state.languages || []).map(function (item) { return item.code; }),
    ]);
    if (sig === bodySig) return;
    bodySig = sig;
    body.innerHTML = "";

    if (TP.ui.settingsTab === "general") {
      const rows = [];

      const languages = state.languages || [];
      if (languages.length > 1) {
        const picker = TP.select({
          options: languages.map(function (item) {
            return { value: item.code, label: item.label };
          }),
          value: state.language,
          onChange: function (code) {
            switchLanguage(code);
          },
        });
        rows.push(row(T("settings.language"), "", picker));
      } else {
        const label = el("span", { class: "meta-text", text: languages.length ? languages[0].label : "" });
        rows.push(row(T("settings.language"), T("settings.language.single"), label));
      }

      const wrapSwitch = TP.switchNode({
        checked: !!state.wrap,
        onChange: function (on) {
          call("update_settings", { wrap: on }).then(function (snapshot) {
            if (snapshot) TP.apply(snapshot);
          });
        },
      });
      rows.push(row(T("settings.wrap"), T("settings.wrap.desc"), wrapSwitch));

      body.appendChild(card(rows));
      return;
    }

    if (TP.ui.settingsTab === "appearance") {
      const seg = el("div", { class: "seg", style: "width:200px" });
      [
        { value: "light", label: T("settings.theme.light") },
        { value: "dark", label: T("settings.theme.dark") },
      ].forEach(function (item) {
        const button = el("button", {
          class: "seg-item" + (state.theme === item.value ? " is-active" : ""),
          type: "button",
          text: item.label,
        });
        button.addEventListener("click", function () {
          if (state.theme === item.value) return;
          TP.setTheme(item.value);
          TP.$$(".seg-item", seg).forEach(function (node) {
            node.classList.toggle("is-active", node === button);
          });
          call("update_settings", { theme: item.value }).then(function (snapshot) {
            if (snapshot) TP.apply(snapshot);
          });
        });
        seg.appendChild(button);
      });
      body.appendChild(card([row(T("settings.theme"), "", seg)]));
      return;
    }

    if (TP.ui.settingsTab === "data") {
      const openBtn = el("button", { class: "btn sm", type: "button", text: T("settings.data.open") });
      openBtn.addEventListener("click", function () {
        call("open_data_dir");
      });
      const dirRow = row(T("settings.data.dir"), "", openBtn);
      dirRow.querySelector(".row-label").appendChild(
        el("span", { class: "path-text", text: state.data_dir })
      );

      const recycleBtn = el("button", { class: "btn sm", type: "button", text: T("settings.data.open") });
      recycleBtn.addEventListener("click", function () {
        call("open_recycle");
      });
      const recycleRow = row(T("settings.data.recycle"), T("settings.data.recycle.desc"), recycleBtn);

      body.appendChild(card([dirRow, recycleRow]));
      return;
    }

    /* 关于 */
    const versionRow = row(T("settings.version"), "", el("span", { class: "meta-text", text: state.version }));
    const resetBtn = el("button", { class: "btn sm danger-ghost", type: "button", text: T("settings.reset") });
    resetBtn.addEventListener("click", function () {
      TP.confirm({
        title: T("settings.reset"),
        text: T("settings.reset.desc"),
        ok: T("common.confirm"),
        danger: true,
      }).then(function (ok) {
        if (!ok) return;
        call("reset_settings").then(function (snapshot) {
          if (!snapshot) return;
          TP.setTheme(snapshot.theme);
          TP.apply(snapshot);
        });
      });
    });
    body.appendChild(
      card([versionRow, row(T("settings.reset"), T("settings.reset.desc"), resetBtn)])
    );
  }

  function switchLanguage(code) {
    call("set_language", code).then(function (snapshot) {
      if (!snapshot) return;
      return TP.loadStrings().then(function () {
        TP.applyStrings();
        TP.apply(snapshot);
        renderNav();
        renderBody();
      });
    });
  }

  function openPage() {
    TP.switchView("settings");
    navSig = "";
    bodySig = "";
    renderNav();
    renderBody();
  }

  function bind() {
    $("#set-back").addEventListener("click", function () {
      TP.switchView("main");
    });
  }

  TP.openSettings = openPage;
  TP.renderSettings = function () {
    if (TP.ui.view !== "settings") return;
    renderNav();
    renderBody();
  };
  TP.bindSettings = bind;
})(window.TP);
