/* 设置：一个弹窗装完。项目不多，不值得为它开一整页。 */

(function (TP) {
  "use strict";

  const el = TP.el;
  const esc = TP.esc;
  const T = TP.T;
  const call = TP.call;

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

  function smallButton(label, onClick, extra) {
    const node = el("button", {
      class: "btn sm" + (extra ? " " + extra : ""),
      type: "button",
      text: label,
    });
    node.addEventListener("click", onClick);
    return node;
  }

  function openSettings() {
    const list = el("div", { class: "settings-list" });
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
            onChange: function (code) {
              call("set_language", code).then(function (snapshot) {
                if (!snapshot) return null;
                return TP.loadStrings().then(function () {
                  TP.applyStrings();
                  TP.apply(snapshot);
                });
              });
            },
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
              label: value ? TP.number(value) + " 字" : T("settings.display.none"),
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

    /* 数据目录 */
    const dirRow = row(T("settings.data.dir"), state.data_dir, null);
    const dirTools = el("div", { style: "display:flex;gap:8px;flex:none" });
    dirTools.appendChild(smallButton(T("settings.data.change"), changeDataDir));
    dirTools.appendChild(
      smallButton(T("settings.data.open"), function () {
        call("open_data_dir");
      })
    );
    dirRow.querySelector(".row-control").appendChild(dirTools);
    list.appendChild(dirRow);

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

    TP.openModal({
      title: T("settings.title"),
      body: list,
      actions: [{ label: T("common.close"), value: true, primary: true }],
    });
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

  function changeDataDir() {
    const input = el("input", { class: "input", type: "text", spellcheck: "false" });
    input.value = TP.state.data_dir || "";
    const browse = smallButton(T("settings.data.browse"), function () {
      call("browse_folder").then(function (result) {
        if (result && result.ok && result.path) input.value = result.path;
      });
    });
    const tools = el("div", { style: "display:flex;gap:8px" });
    tools.appendChild(input);
    tools.appendChild(browse);

    const field = el("div", { class: "field" });
    field.appendChild(el("span", { class: "field-label", text: T("settings.data.dir") }));
    field.appendChild(tools);
    field.appendChild(el("span", { class: "field-hint", text: T("settings.data.change.hint") }));

    TP.openModal({
      title: T("settings.data.change.title"),
      body: field,
      actions: [
        { label: T("common.cancel"), value: null, ghost: true },
        {
          label: T("common.confirm"),
          value: true,
          primary: true,
          onClick: function (ctx) {
            const value = input.value.trim();
            if (!value) return false;
            ctx.setActions([{ label: T("common.confirm"), disabled: true }]);
            call("set_data_dir", value).then(function (snapshot) {
              ctx.close(true);
              if (!snapshot) return;
              TP.apply(snapshot);
              if (snapshot.pending_dir) askRestart();
            });
            return false;
          },
        },
      ],
    });
    setTimeout(function () {
      input.focus();
      input.select();
    }, 60);
  }

  function askRestart() {
    TP.openModal({
      title: T("settings.data.restart.title"),
      size: "narrow",
      body: "<p>" + esc(T("settings.data.restart.text")) + "</p>",
      dismissible: false,
      actions: [
        { label: T("settings.data.restart.later"), value: false, ghost: true },
        {
          label: T("settings.data.restart.now"),
          value: true,
          primary: true,
          onClick: function () {
            call("restart_app");
            return false;
          },
        },
      ],
    });
  }

  TP.openSettings = openSettings;
})(window.TP);
