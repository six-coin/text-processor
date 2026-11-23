/* 设置：一个弹窗装完。项目不多，不值得为它开一整页。 */

(function (TP) {
  "use strict";

  const el = TP.el;
  const esc = TP.esc;
  const T = TP.T;
  const call = TP.call;

  //: 当前打开的设置弹窗，换语言时要原地重画。
  let settingsCtx = null;

  function row(label, hint, control, foot) {
    const node = el("div", { class: "card-row" + (foot ? " has-foot" : "") });
    const box = el("div", { class: "row-label" });
    box.appendChild(el("strong", { text: label }));
    if (hint) box.appendChild(el("span", { text: hint }));
    node.appendChild(box);
    const holder = el("div", { class: "row-control" });
    if (control) holder.appendChild(control);
    node.appendChild(holder);
    // 行末的通栏说明：数据目录那一行用它放「重启后生效」和「立即重启」。
    if (foot) node.appendChild(foot);
    return node;
  }

  function smallButton(label, onClick, extra) {
    const node = el("button", {
      class: "btn sm" + (extra ? " " + extra : ""),
      type: "button",
      text: label,
    });
    node.addEventListener("click", onClick);
    return node;
  }

  function buildRows(list) {
    const state = TP.state;

    /* 界面语言 */
    const languages = state.languages || [];
    if (languages.length > 1) {
      list.appendChild(
        row(
          T("settings.language"),
          "",
          TP.select({
            options: languages.map(function (item) {
              return { value: item.code, label: item.label };
            }),
            value: state.language,
            onChange: switchLanguage,
          })
        )
      );
    } else {
      list.appendChild(
        row(
          T("settings.language"),
          T("settings.language.single"),
          el("span", { class: "meta-text", text: languages.length ? languages[0].label : "" })
        )
      );
    }

    /* 主题 */
    const seg = el("div", { class: "seg", style: "width:190px" });
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
        if (TP.state.theme === item.value) return;
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
    list.appendChild(row(T("settings.theme"), "", seg));

    /* 自动换行 */
    list.appendChild(
      row(
        T("settings.wrap"),
        T("settings.wrap.desc"),
        TP.switchNode({
          checked: !!state.wrap,
          onChange: function (on) {
            call("update_settings", { wrap: on }).then(function (snapshot) {
              if (snapshot) TP.apply(snapshot);
            });
          },
        })
      )
    );

    /* 正文显示上限 */
    const limits = [5000, 10000, 20000, 50000, 0];
    list.appendChild(
      row(
        T("settings.display"),
        T("settings.display.desc"),
        TP.select({
          options: limits.map(function (value) {
            return {
              value: String(value),
              label: value ? TP.number(value) + " " + T("unit.chars") : T("settings.display.none"),
            };
          }),
          value: String(state.display_limit || 0),
          onChange: function (value) {
            call("update_settings", { display_limit: Number(value) }).then(function (snapshot) {
              if (snapshot) TP.apply(snapshot);
            });
          },
        })
      )
    );

    /* 正文字体 */
    list.appendChild(
      row(
        T("settings.font_family"),
        T("settings.font_family.desc"),
        TP.select({
          options: TP.FONT_KEYS.map(function (key) {
            return { value: key, label: T("font." + key) };
          }),
          value: state.doc_font || "default",
          onChange: function (value) {
            call("update_settings", { doc_font: value }).then(function (snapshot) {
              if (snapshot) TP.apply(snapshot);
            });
          },
        })
      )
    );

    /* 正文字号 */
    const sizes = [13, 14.5, 16, 18, 20];
    list.appendChild(
      row(
        T("settings.font"),
        T("settings.font.desc"),
        TP.select({
          options: sizes.map(function (value) {
            return { value: String(value), label: value + " px" };
          }),
          value: String(state.font_size || 14.5),
          onChange: function (value) {
            call("update_settings", { font_size: Number(value) }).then(function (snapshot) {
              if (snapshot) TP.apply(snapshot);
            });
          },
        })
      )
    );

    /* 外观与日志之间：一条淡细线，不要逐条画 */
    list.appendChild(el("div", { class: "settings-divider" }));

    /* 日志级别：与语言同一套下拉框，四个值不会把一行撑开 */
    list.appendChild(
      row(
        T("settings.log_level"),
        T("settings.log_level.desc"),
        TP.select({
          options: (state.log_levels || []).map(function (item) {
            return { value: item.value, label: item.label };
          }),
          value: state.log_level || "INFO",
          onChange: function (value) {
            call("update_settings", { log_level: value }).then(function (snapshot) {
              if (snapshot) TP.apply(snapshot);
            });
          },
        })
      )
    );

    /* 自动清空日志 */
    list.appendChild(
      row(
        T("settings.log_cleanup"),
        T("settings.log_cleanup.desc"),
        TP.switchNode({
          checked: state.log_cleanup !== false,
          onChange: function (on) {
            call("update_settings", { log_cleanup: on }).then(function (snapshot) {
              if (snapshot) TP.apply(snapshot);
            });
          },
        })
      )
    );

    /* 日志保留天数 */
    const logDays = el("input", {
      class: "input",
      type: "number",
      min: "1",
      max: "365",
      step: "1",
    });
    logDays.value = String(state.log_retention_days || 30);
    logDays.addEventListener("change", function () {
      const value = Number(logDays.value);
      if (!Number.isFinite(value)) {
        logDays.value = String(TP.state.log_retention_days || 30);
        return;
      }
      call("update_settings", { log_retention_days: value }).then(function (snapshot) {
        if (!snapshot) return;
        TP.apply(snapshot);
        // 后端会夹取，输入框跟着回正，别让界面显示一个没生效的数字。
        logDays.value = String(snapshot.log_retention_days);
      });
    });
    list.appendChild(row(T("settings.log_days"), T("settings.log_days.desc"), logDays));

    /* 其他块之前再加一条分隔线 */
    list.appendChild(el("div", { class: "settings-divider" }));

    /* 数据目录：输入框 + 更改 + 重置，下面一行写清「重启后生效」和「立即重启」 */
    const dirInput = el("input", { class: "input", type: "text", spellcheck: "false" });
    // 输入框里是「重启后生效的落点」，没有待生效的值就是当前目录。
    dirInput.value = state.data_dir_next || state.data_dir || "";
    dirInput.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;
      event.preventDefault();
      applyDataDirValue(dirInput.value);
    });
    const dirTools = el("div", { class: "row-tools" });
    dirTools.appendChild(dirInput);
    dirTools.appendChild(
      smallButton(T("settings.data.change"), function () {
        changeDataDir(dirInput.value);
      })
    );
    dirTools.appendChild(smallButton(T("settings.data.reset"), resetDataDir));
    // 重启按钮和重置放在一起，不要塞进下面的说明行。
    if (state.data_dir_next) {
      dirTools.appendChild(smallButton(T("settings.data.restart"), restartApp));
    }
    list.appendChild(row(T("settings.data.dir"), "", dirTools, dataDirFoot()));

    /* 回收站 */
    list.appendChild(
      row(
        T("settings.data.recycle"),
        T("settings.data.recycle.desc"),
        smallButton(T("settings.data.open"), function () {
          call("open_recycle");
        })
      )
    );

    /* 使用说明 */
    list.appendChild(
      row(
        T("settings.manual"),
        T("settings.manual.desc"),
        smallButton(T("settings.manual.open"), showManual)
      )
    );

    /* 版本 */
    list.appendChild(
      row(T("settings.version"), "", el("span", { class: "meta-text", text: state.version }))
    );

    /* 恢复默认 */
    list.appendChild(
      row(
        T("settings.reset"),
        T("settings.reset.desc"),
        smallButton(T("settings.reset.action"), resetAll, "danger-ghost")
      )
    );
  }

  /** 数据目录下面那一行：待生效的落点、上次迁移的结果，或者一句默认说明。 */
  function dataDirFoot() {
    const foot = el("div", { class: "card-row-foot" });
    foot.appendChild(el("span", { class: "row-hint", text: dataDirHint(TP.state) }));
    return foot;
  }

  function dataDirHint(state) {
    const status = state.data_dir_status || {};
    if (state.data_dir_next) {
      return status.status === "failed"
        ? T("settings.data.pending_failed", { path: state.data_dir_next })
        : T("settings.data.pending", { path: state.data_dir_next });
    }
    if (status.status === "done" && status.moved > 0) {
      return T("settings.data.migrated", { count: status.moved, path: state.data_dir });
    }
    return T("settings.data.change.hint");
  }

  /** 立即重启：数据目录的搬迁只发生在启动早期，改完目录必须真重启一次。 */
  function restartApp() {
    call("restart_app");
  }

  function openSettings() {
    const list = el("div", { class: "settings-list" });
    buildRows(list);
    TP.openModal({
      title: T("settings.title"),
      body: list,
      size: "wide",
      actions: [{ label: T("common.close"), value: true, primary: true }],
      onMount: function (ctx) {
        settingsCtx = ctx;
      },
    });
  }

  /** 换语言后原地重画，不要关掉再开。 */
  function rebuild() {
    if (!settingsCtx || !settingsCtx.modal.isConnected) return;
    const list = el("div", { class: "settings-list" });
    buildRows(list);
    settingsCtx.setTitle(T("settings.title"));
    settingsCtx.setBody(list);
    settingsCtx.setActions([{ label: T("common.close"), value: true, primary: true }]);
  }

  function switchLanguage(code) {
    call("set_language", code).then(function (snapshot) {
      if (!snapshot) return null;
      return TP.loadStrings().then(function () {
        TP.applyStrings();
        TP.apply(snapshot);
        rebuild();
      });
    });
  }

  function showManual() {
    call("get_readme").then(function (result) {
      if (!result || !result.ok) return;
      TP.openModal({
        title: T("settings.manual"),
        size: "wide",
        body: el("div", { html: TP.renderMarkdown(trimManual(result.markdown)) }),
        actions: [{ label: T("common.close"), value: true, primary: true }],
      });
    });
  }

  /** 去掉手册开头的大标题：弹窗标题已经说明这是什么。 */
  function trimManual(markdown) {
    return String(markdown || "")
      .split("\n")
      .filter(function (line) {
        return !/^#\s/.test(line);
      })
      .join("\n");
  }

  function resetAll() {
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
  }

  /** 更改：输入框改过就按输入的落点走，没改过才去选目录。 */
  function changeDataDir(raw) {
    const typed = String(raw || "").trim();
    const current = String(TP.state.data_dir_next || TP.state.data_dir || "").trim();
    if (typed && typed !== current) {
      applyDataDirValue(typed);
      return;
    }
    call("browse_folder").then(function (result) {
      if (result && result.ok && result.path) applyDataDirValue(result.path);
    });
  }

  function applyDataDirValue(value) {
    const text = String(value || "").trim();
    if (!text) return;
    call("set_data_dir", text).then(applyDataDir);
  }

  function resetDataDir() {
    call("set_data_dir", TP.state.data_dir_default || "").then(applyDataDir);
  }

  /** 更改数据目录之后的统一收尾：落快照、重画设置页、状态栏说一句。 */
  function applyDataDir(snapshot) {
    if (!snapshot) return;
    // 提示由 TP.apply() 统一弹一次，这里再弹就重复了。
    TP.apply(snapshot);
    rebuild();
  }

  TP.openSettings = openSettings;
})(window.TP);
