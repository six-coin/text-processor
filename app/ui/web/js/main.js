/* 启动、状态应用、全局快捷键、关闭握手。 */

(function (TP) {
  "use strict";

  const $ = TP.$;
  const T = TP.T;
  const call = TP.call;

  let booted = false;

  /* ---------------------------------------------------------------- 文案 */

  function loadStrings() {
    return call("get_strings").then(function (result) {
      if (result && result.strings) {
        TP.strings = result.strings;
        TP.applyStrings();
      }
      return result;
    });
  }

  /* ---------------------------------------------------------------- 应用快照 */

  function apply(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return;
    const previous = TP.state;

    // 正文可能很大，只在真的变了的时候下发；没下发就沿用上一份。
    if (!("text" in snapshot) && previous && "text" in previous) {
      snapshot.text = previous.text;
      snapshot.text_meta = previous.text_meta;
    }

    TP.state = snapshot;

    if (snapshot.theme) TP.setTheme(snapshot.theme);

    const changedProject =
      !previous ||
      !previous.current ||
      !snapshot.current ||
      previous.current.id !== snapshot.current.id;
    if (changedProject) {
      TP.ui.lastVersionCount = snapshot.versions ? snapshot.versions.length : 0;
      TP.ui.lastBaseIndex = 0;
      if (TP.ui.find.open) TP.setFindOpen(false);
      if (TP.ui.draft) {
        TP.ui.draft = null;
        TP.ui.dirty = false;
      }
    }

    TP.renderProjects();
    TP.renderDoc();
    TP.renderRail();
    if (TP.ui.view === "processors") TP.renderProcessors();

    if (snapshot.message) TP.toast(snapshot.message, snapshot.ok === false);
  }

  /* ---------------------------------------------------------------- 关闭握手 */

  TP.hostAskClose = function () {
    TP.openModal({
      title: T("close.title"),
      size: "narrow",
      body: "<p>" + TP.esc(T("close.text")) + "</p>",
      dismissible: false,
      actions: [
        { label: T("close.stay"), value: false, ghost: true },
        {
          label: T("close.discard"),
          value: true,
          danger: true,
          onClick: function () {
            call("answer_close", "close");
            return false;
          },
        },
      ],
    });
  };

  /* ---------------------------------------------------------------- 绑定 */

  function toggleTheme() {
    const next = TP.state && TP.state.theme === "dark" ? "light" : "dark";
    TP.setTheme(next);
    call("update_settings", { theme: next }).then(function (snapshot) {
      if (snapshot) TP.apply(snapshot);
    });
  }

  function onKeydown(event) {
    const mod = event.ctrlKey || event.metaKey;
    if (mod && event.key.toLowerCase() === "n") {
      if (TP.ui.view !== "main") return;
      event.preventDefault();
      TP.newProject();
      return;
    }
    if (mod && event.key.toLowerCase() === "f") {
      if (TP.ui.view !== "main" || !TP.hasProject()) return;
      event.preventDefault();
      TP.setFindOpen(true);
      return;
    }
    if (event.key === "Escape" && TP.ui.find.open) {
      TP.setFindOpen(false);
    }
  }

  function bind() {
    TP.bindMain();
    TP.bindProcessors();
    $("#btn-theme").addEventListener("click", toggleTheme);
    $("#btn-settings").addEventListener("click", function () {
      TP.openSettings();
    });
    document.addEventListener("keydown", onKeydown);
  }

  /* ---------------------------------------------------------------- 启动 */

  function boot() {
    if (booted) return;
    if (!window.pywebview || !window.pywebview.api) return;
    booted = true;
    loadStrings()
      .then(function () {
        return call("get_state");
      })
      .then(function (snapshot) {
        bind();
        if (snapshot) apply(snapshot);
      })
      .catch(function (error) {
        TP.toast(T("error.generic", { error: error }), true);
      });
  }

  TP.loadStrings = loadStrings;
  TP.apply = apply;

  window.addEventListener("pywebviewready", boot);
  document.addEventListener("DOMContentLoaded", function () {
    setTimeout(boot, 0);
  });
  setTimeout(boot, 300);
  setTimeout(boot, 1200);
})(window.TP);
