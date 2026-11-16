/* 覆盖层：新建项目、处理器参数、改动评审、手动修改、AI 向导。 */

(function (TP) {
  "use strict";

  const el = TP.el;
  const T = TP.T;
  const esc = TP.esc;
  const call = TP.call;

  /* ---------------------------------------------------------------- 工具 */

  function fieldRow(labelText, control, hint) {
    const wrap = el("label", { class: "field" });
    wrap.appendChild(el("span", { class: "field-label", text: labelText }));
    wrap.appendChild(control);
    if (hint) wrap.appendChild(el("span", { class: "field-hint", text: hint }));
    return wrap;
  }

  function showFieldError(control, message) {
    control.classList.add("invalid");
    const field = control.closest(".field");
    if (!field) return;
    const old = field.querySelector(".field-error");
    if (old) old.remove();
    field.appendChild(el("span", { class: "field-error", text: message }));
    control.focus();
  }

  function clearFieldError(control) {
    control.classList.remove("invalid");
    const field = control.closest(".field");
    if (field) {
      const old = field.querySelector(".field-error");
      if (old) old.remove();
    }
  }

  function emptyLine() {
    return '<span style="color:var(--muted)">（空行）</span>';
  }

  /** 只有空白字符的默认值在输入框里看不见，补一句说明。 */
  function blankHint(value) {
    if (typeof value !== "string" || !value.length || value.trim() !== "") return "";
    return T("run.blank_hint", { n: value.length });
  }

  function segmentHtml(list, kind) {
    if (!list || !list.length) return emptyLine();
    const plain = list
      .map(function (item) {
        return item[0] || "";
      })
      .join("");
    if (!plain.length) return emptyLine();
    // 整行都是空白时把空白画出来，否则用户只会看到一块没有内容的色块。
    const blank = plain.trim() === "";
    const html = list
      .map(function (item) {
        let text = item[0] || "";
        if (!text) return "";
        if (blank) text = text.replace(/ /g, "·").replace(/\t/g, "⇥");
        if (!item[1]) return esc(text);
        return '<span class="seg-' + kind + '">' + esc(text) + "</span>";
      })
      .join("");
    return html || emptyLine();
  }

  /* ---------------------------------------------------------------- 新建项目 */

  function newProject() {
    const body = el("div", { class: "form-grid" });
    const name = el("input", {
      class: "input",
      id: "np-name",
      type: "text",
      maxlength: "40",
      placeholder: T("project.new.name.placeholder"),
    });
    const text = el("textarea", {
      class: "textarea",
      id: "np-text",
      style: "height:260px;font-family:Consolas,'Cascadia Mono',monospace;font-size:13px;",
      placeholder: T("project.new.text.placeholder"),
    });
    const importBtn = el("button", {
      class: "btn sm",
      type: "button",
      text: T("project.new.import"),
    });
    importBtn.addEventListener("click", function () {
      importBtn.disabled = true;
      call("import_text").then(function (result) {
        importBtn.disabled = false;
        if (!result || result.cancelled) return;
        if (!result.ok) {
          TP.toast(T("project.new.import.failed", { error: result.message || "" }), true);
          return;
        }
        text.value = result.text || "";
        clearFieldError(text);
        TP.toast(T("project.new.imported", { name: result.name, n: TP.number(result.chars) }));
      });
    });

    const textField = el("div", { class: "field" });
    const textLabel = el("div", { class: "field-label" });
    textLabel.appendChild(el("span", { text: T("project.new.text") }));
    textLabel.appendChild(el("span", { style: "flex:1" }));
    textLabel.appendChild(importBtn);
    textField.appendChild(textLabel);
    textField.appendChild(text);

    body.appendChild(fieldRow(T("project.new.name"), name));
    body.appendChild(textField);

    TP.openModal({
      title: T("project.new.title"),
      size: "wide",
      body: body,
      actions: [
        { label: T("common.cancel"), value: false, ghost: true },
        {
          label: T("common.confirm"),
          value: true,
          primary: true,
          onClick: function (ctx) {
            const title = name.value.trim();
            const content = text.value;
            if (!title) {
              showFieldError(name, T("project.new.empty_name"));
              return false;
            }
            if (!content.trim()) {
              showFieldError(text, T("project.new.empty_text"));
              return false;
            }
            ctx.setActions([{ label: T("common.confirm"), disabled: true }]);
            call("create_project", title, content).then(function (snapshot) {
              ctx.close(true);
              if (snapshot) TP.apply(snapshot);
            });
            return false;
          },
        },
      ],
    });
  }

  /* ---------------------------------------------------------------- 处理器参数 */

  function runProcessor(processor) {
    const body = el("div", { class: "form-grid" });
    const inputs = {};
    const last = processor.last && processor.last.params ? processor.last.params : {};
    const lastCompare = !!(processor.last && processor.last.compare);

    processor.args.forEach(function (arg) {
      const preset =
        last[arg.id] !== undefined && last[arg.id] !== null ? last[arg.id] : arg.default;
      let control = null;

      if (arg.type === "bool") {
        const row = el("div", { class: "switch-row" });
        const labelBox = el("div", { class: "row-label" });
        labelBox.appendChild(el("strong", { text: arg.name }));
        if (arg.desc) labelBox.appendChild(el("span", { text: arg.desc }));
        const toggle = TP.switchNode({ checked: !!preset });
        row.appendChild(labelBox);
        row.appendChild(toggle);
        body.appendChild(row);
        inputs[arg.id] = { kind: "bool", node: toggle, arg: arg };
        return;
      }

      if (arg.type === "choice") {
        const picker = TP.select({
          options: arg.options.map(function (option) {
            return { value: option.value, label: option.label };
          }),
          value: String(preset),
        });
        body.appendChild(fieldRow(arg.name, picker, arg.desc));
        inputs[arg.id] = { kind: "choice", node: picker, arg: arg };
        return;
      }

      if (arg.type === "text") {
        control = el("textarea", { class: "textarea", style: "height:88px" });
        control.value = String(preset == null ? "" : preset);
      } else if (arg.type === "int" || arg.type === "float") {
        control = el("input", {
          class: "input",
          type: "text",
          inputmode: "numeric",
          autocomplete: "off",
        });
        control.value = String(preset == null ? "" : preset);
      } else {
        control = el("input", { class: "input", type: "text", autocomplete: "off" });
        control.value = String(preset == null ? "" : preset);
      }

      const hint = [];
      if (arg.desc) hint.push(arg.desc);
      if (arg.min != null || arg.max != null) {
        hint.push(
          T("run.range", {
            min: arg.min != null ? arg.min : "−∞",
            max: arg.max != null ? arg.max : "∞",
          })
        );
      }
      const blanks = blankHint(String(preset == null ? "" : preset));
      if (blanks) hint.push(blanks);
      body.appendChild(fieldRow(arg.name, control, hint.join(" · ")));
      inputs[arg.id] = { kind: "text", node: control, arg: arg };
    });

    let compareNode = null;
    if (processor.type === "line") {
      const row = el("div", { class: "switch-row" });
      const labelBox = el("div", { class: "row-label" });
      labelBox.appendChild(el("strong", { text: T("run.compare") }));
      labelBox.appendChild(el("span", { text: T("run.compare.desc") }));
      compareNode = TP.switchNode({ checked: lastCompare });
      row.appendChild(labelBox);
      row.appendChild(compareNode);
      body.appendChild(row);
    }

    if (!processor.args.length && !compareNode) {
      body.appendChild(el("p", { class: "field-hint", text: T("run.no_args") }));
    }

    TP.openModal({
      title: processor.name,
      subtitle: processor.desc,
      body: body,
      actions: [
        { label: T("common.cancel"), value: false, ghost: true },
        {
          label: T("common.confirm"),
          value: true,
          primary: true,
          onClick: function (ctx) {
            const params = {};
            let bad = null;
            Object.keys(inputs).forEach(function (key) {
              const item = inputs[key];
              if (item.kind === "bool") {
                params[key] = item.node.isChecked();
                return;
              }
              if (item.kind === "choice") {
                params[key] = item.node.getValue();
                return;
              }
              const raw = item.node.value;
              if (item.arg.type === "int" || item.arg.type === "float") {
                const number = Number(raw === "" ? item.arg.default : raw);
                if (!isFinite(number)) {
                  bad = bad || { node: item.node, message: "请填一个数字" };
                  return;
                }
                params[key] = item.arg.type === "int" ? Math.round(number) : number;
                return;
              }
              params[key] = raw;
            });
            if (bad) {
              showFieldError(bad.node, bad.message);
              return false;
            }
            const compare = compareNode ? compareNode.isChecked() : false;
            ctx.setActions([{ label: T("common.confirm"), disabled: true }]);
            call("apply_processor", processor.id, params, compare).then(function (snapshot) {
              ctx.close(true);
              if (!snapshot) return;
              TP.apply(snapshot);
              if (snapshot.review) TP.openReview(snapshot.review);
            });
            return false;
          },
        },
      ],
    });
  }

  /* ---------------------------------------------------------------- 改动评审 */

  function openReview(payload) {
    if (!payload) return;
    const isCheck = payload.kind === "check";
    const rows = [];
    const body = el("div");

    const summary = el("div", { class: "review-summary" });
    summary.appendChild(
      el("span", {
        text: T(isCheck ? "review.summary.check" : "review.summary.line", { n: payload.count }),
      })
    );
    body.appendChild(summary);

    const list = el("div", { class: "review-list" });
    body.appendChild(list);

    if (payload.omitted) {
      body.appendChild(
        el("p", { class: "field-hint", style: "margin-top:10px", text: T("review.omitted", { n: payload.omitted }) })
      );
    }

    payload.items.forEach(function (item) {
      const row = el("div", { class: "review-row" });
      const head = el("div", { class: "review-head" });
      head.appendChild(el("span", { class: "review-line", text: T("review.line", { n: item.index + 1 }) }));
      if (isCheck) {
        head.appendChild(el("span", { class: "review-reason", text: item.reason || "" }));
      }
      const toggle = TP.switchNode({
        checked: true,
        onChange: function (on) {
          row.classList.toggle("is-kept", !on);
        },
      });
      head.appendChild(toggle);
      row.appendChild(head);

      const content = el("div", { class: "review-body" });
      if (isCheck) {
        const input = el("input", { class: "review-input", type: "text", value: item.text });
        content.appendChild(input);
        rows.push({ index: item.index, toggle: toggle, input: input });
      } else {
        content.innerHTML =
          '<div class="review-line-text"><span class="label">原</span>' +
          segmentHtml(item.a, "del") +
          "</div>" +
          '<div class="review-line-text"><span class="label">新</span>' +
          segmentHtml(item.b, "add") +
          "</div>";
        rows.push({ index: item.index, toggle: toggle, input: null });
      }
      row.appendChild(content);
      list.appendChild(row);
    });

    function setAll(value) {
      rows.forEach(function (row) {
        row.toggle.setChecked(value);
        const node = row.toggle.closest(".review-row");
        if (node) node.classList.toggle("is-kept", !value);
      });
    }

    TP.openModal({
      title: T(isCheck ? "review.title.check" : "review.title.line"),
      subtitle: payload.title,
      size: "wide",
      body: body,
      dismissible: false,
      actions: [
        { label: T("review.apply_all"), align: "left", ghost: true, onClick: function () { setAll(true); return false; }, keepOpen: true },
        { label: T("review.keep_all"), align: "left", ghost: true, onClick: function () { setAll(false); return false; }, keepOpen: true },
        {
          label: T("common.cancel"),
          value: null,
          ghost: true,
          onClick: function (ctx) {
            call("cancel_review", payload.token).then(function (snapshot) {
              ctx.close(null);
              if (snapshot) TP.apply(snapshot);
            });
            return false;
          },
        },
        {
          label: T("common.confirm"),
          value: true,
          primary: true,
          onClick: function (ctx) {
            const decisions = rows.map(function (row) {
              const item = { index: row.index, apply: row.toggle.isChecked() };
              if (isCheck && row.input) item.text = row.input.value;
              return item;
            });
            ctx.setActions([{ label: T("common.confirm"), disabled: true }]);
            call("commit_review", payload.token, decisions).then(function (snapshot) {
              ctx.close(true);
              if (snapshot) TP.apply(snapshot);
            });
            return false;
          },
        },
      ],
    });
  }

  /* ---------------------------------------------------------------- 手动修改 */

  function manualEdit() {
    if (!TP.hasProject()) {
      TP.toast(T("error.no_project"), true);
      return;
    }
    if (TP.inPreview()) {
      TP.toast(T("error.preview"), true);
      return;
    }

    const current = TP.state.current;
    const body = el("div", {
      style: "display:flex;flex-direction:column;height:100%;min-height:0",
    });

    const bar = el("div", { class: "manual-bar" });
    const externalBtn = el("button", { class: "btn sm", type: "button", text: T("manual.external") });
    const reloadBtn = el("button", { class: "btn sm", type: "button", text: T("manual.reload") });
    reloadBtn.disabled = true;
    const status = el("span", { class: "status", text: T("manual.desc") });
    bar.appendChild(externalBtn);
    bar.appendChild(reloadBtn);
    bar.appendChild(status);

    const area = el("textarea", { class: "plain-editor", spellcheck: "false" });
    area.style.height = "auto";
    area.style.flex = "1";
    area.style.minHeight = "0";
    area.value = TP.state.text || "";

    body.appendChild(bar);
    body.appendChild(area);

    let external = false;

    externalBtn.addEventListener("click", function () {
      externalBtn.disabled = true;
      call("external_edit", area.value).then(function (result) {
        if (!result || !result.ok) {
          externalBtn.disabled = false;
          TP.toast(T("manual.external.failed"), true);
          return;
        }
        external = true;
        area.readOnly = true;
        reloadBtn.disabled = false;
        status.textContent = T("manual.external.opened");
        status.classList.add("is-on");
        reloadBtn.focus();
      });
    });

    reloadBtn.addEventListener("click", function () {
      reloadBtn.disabled = true;
      call("read_external").then(function (result) {
        reloadBtn.disabled = false;
        if (!result || !result.ok) {
          TP.toast(T("manual.failed", { error: (result && result.message) || "" }), true);
          return;
        }
        area.value = result.text || "";
        TP.toast(T("manual.reloaded"));
      });
    });

    function save(ctx) {
      ctx.setActions([{ label: T("common.save"), disabled: true }]);
      // 外部编辑模式下先把磁盘上的最新内容读回来，免得用户忘了点「重新读取」。
      const latest = external
        ? call("read_external").then(function (result) {
            return result && result.ok ? result.text : area.value;
          })
        : Promise.resolve(area.value);

      latest
        .then(function (text) {
          return call("save_manual", text);
        })
        .then(function (snapshot) {
          ctx.close(true);
          if (snapshot) TP.apply(snapshot);
        });
    }

    TP.openModal({
      title: T("manual.title"),
      subtitle:
        T("doc.version", { n: current.index }) + (current.title ? " · " + current.title : ""),
      size: "xl",
      body: body,
      actions: [
        { label: T("common.cancel"), value: null, ghost: true },
        {
          label: T("common.save"),
          value: true,
          primary: true,
          onClick: function (ctx) {
            save(ctx);
            return false;
          },
        },
      ],
    });

    setTimeout(function () {
      area.focus();
      area.setSelectionRange(0, 0);
      area.scrollTop = 0;
    }, 60);
  }

  /* ---------------------------------------------------------------- AI 向导 */

  function aiWizard() {
    const body = el("div");

    const step1 = el("div", { class: "ai-step" });
    const head1 = el("div", { class: "ai-step-head" });
    head1.appendChild(el("span", { class: "step-no", text: "1" }));
    head1.appendChild(el("span", { text: T("ai.step1") }));
    const request = el("textarea", {
      class: "textarea",
      style: "height:84px",
      placeholder: T("ai.request.placeholder"),
    });
    const copyRow = el("div", { style: "display:flex;align-items:center;gap:10px;margin-top:8px" });
    const copyBtn = el("button", { class: "btn primary", type: "button", text: T("ai.copy") });
    const previewBtn = el("button", { class: "btn ghost", type: "button", text: T("ai.preview") });
    copyRow.appendChild(copyBtn);
    copyRow.appendChild(previewBtn);
    step1.appendChild(head1);
    step1.appendChild(request);
    step1.appendChild(copyRow);
    step1.appendChild(el("p", { class: "ai-hint", text: T("ai.hint") }));

    const step2 = el("div", { class: "ai-step" });
    const head2 = el("div", { class: "ai-step-head" });
    head2.appendChild(el("span", { class: "step-no", text: "2" }));
    head2.appendChild(el("span", { text: T("ai.step2") }));
    const code = el("textarea", {
      class: "textarea ai-code",
      placeholder: T("ai.paste.placeholder"),
      spellcheck: "false",
    });
    step2.appendChild(head2);
    step2.appendChild(code);

    body.appendChild(step1);
    body.appendChild(step2);

    let lastPrompt = "";

    function doCopy() {
      const text = request.value.trim();
      if (!text) {
        showFieldError(request, T("ai.need_request"));
        return;
      }
      clearFieldError(request);
      call("ai_prompt", text).then(function (result) {
        if (!result) return;
        lastPrompt = result.prompt || "";
        if (result.ok) {
          step1.classList.add("is-done");
          TP.toast(result.message || T("ai.copied"));
          code.focus();
        } else {
          TP.toast(result.message || T("ai.copy.failed"), true);
        }
      });
    }

    copyBtn.addEventListener("click", doCopy);

    previewBtn.addEventListener("click", function () {
      if (!lastPrompt) {
        doCopy();
        return;
      }
      TP.openModal({
        title: T("ai.preview.title"),
        size: "wide",
        body: el("pre", { class: "ai-preview", text: lastPrompt }),
        actions: [{ label: T("common.close"), value: true, primary: true }],
      });
    });

    TP.openModal({
      title: T("ai.title"),
      size: "wide",
      body: body,
      actions: [
        { label: T("common.cancel"), value: null, ghost: true },
        {
          label: T("ai.save"),
          value: true,
          primary: true,
          onClick: function (ctx) {
            const source = code.value.trim();
            if (!source) {
              showFieldError(code, T("ai.need_code"));
              return false;
            }
            ctx.setActions([{ label: T("ai.save"), disabled: true }]);
            call("create_processor", source).then(function (snapshot) {
              ctx.close(true);
              if (!snapshot) return;
              TP.apply(snapshot);
              if (snapshot.created) {
                TP.ui.processorId = snapshot.created;
                TP.renderProcessors();
              }
            });
            return false;
          },
        },
      ],
    });
  }

  /* ---------------------------------------------------------------- 导出 */

  TP.newProject = newProject;
  TP.runProcessor = runProcessor;
  TP.openReview = openReview;
  TP.manualEdit = manualEdit;
  TP.aiWizard = aiWizard;
})(window.TP);
