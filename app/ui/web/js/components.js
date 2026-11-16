/* 通用组件：弹窗、确认框、自绘下拉、开关。 */

(function (TP) {
  "use strict";

  const el = TP.el;
  const T = TP.T;
  const $ = TP.$;

  /* ---------------------------------------------------------------- 弹窗 */

  const stack = [];

  function activeModal() {
    return stack.length ? stack[stack.length - 1] : null;
  }

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    const top = activeModal();
    if (!top) return;
    event.preventDefault();
    event.stopPropagation();
    if (top.dismissible) top.close(null);
  }, true);

  /**
   * 打开一个弹窗。
   * @param {object} options
   *   title, subtitle, body(HTML 或 Node), actions[{label,value,primary,danger,align,onClick}],
   *   size("" | "narrow" | "wide" | "xl"), dismissible(默认 true), onMount(ctx)
   * @returns {Promise<any>} 关闭时带着被点按钮的 value（点遮罩/Esc 是 null）
   */
  function openModal(options) {
    const config = options || {};
    const dismissible = config.dismissible !== false;

    const modal = el("div", { class: "modal" });
    const card = el("div", { class: "modal-card" + (config.size ? " " + config.size : "") });

    const head = el("div", { class: "modal-head" });
    const headText = el("div");
    const titleNode = el("h2", { text: config.title || "" });
    headText.appendChild(titleNode);
    if (config.subtitle) {
      headText.appendChild(el("p", { class: "meta-text", text: config.subtitle }));
    }
    head.appendChild(headText);
    if (dismissible) {
      const closeBtn = el("button", { class: "icon-btn", type: "button", "aria-label": T("common.close") });
      closeBtn.innerHTML =
        '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>';
      closeBtn.addEventListener("click", function () {
        ctx.close(null);
      });
      head.appendChild(closeBtn);
    }

    const body = el("div", { class: "modal-body" });
    if (typeof config.body === "string") body.innerHTML = config.body;
    else if (config.body) body.appendChild(config.body);

    const foot = el("div", { class: "modal-foot" });

    card.appendChild(head);
    card.appendChild(body);
    card.appendChild(foot);
    modal.appendChild(card);

    const ctx = {
      modal: modal,
      card: card,
      head: head,
      body: body,
      foot: foot,
      dismissible: dismissible,
      close: null,
      setTitle: function (text) {
        titleNode.textContent = text || "";
      },
      setBody: function (content) {
        body.innerHTML = "";
        if (typeof content === "string") body.innerHTML = content;
        else if (content) body.appendChild(content);
      },
      setActions: function (actions) {
        renderActions(actions || []);
      },
    };

    let settled = false;
    let resolveFn = null;
    const promise = new Promise(function (resolve) {
      resolveFn = resolve;
    });

    ctx.close = function (value) {
      if (settled) return;
      settled = true;
      const index = stack.indexOf(ctx);
      if (index >= 0) stack.splice(index, 1);
      modal.classList.add("is-leaving");
      setTimeout(function () {
        modal.remove();
        resolveFn(value);
      }, 170);
    };

    function renderActions(actions) {
      foot.innerHTML = "";
      const left = actions.filter(function (item) {
        return item.align === "left";
      });
      const right = actions.filter(function (item) {
        return item.align !== "left";
      });
      left.forEach(function (item) {
        foot.appendChild(makeAction(item));
      });
      foot.appendChild(el("div", { class: "spacer" }));
      right.forEach(function (item) {
        foot.appendChild(makeAction(item));
      });
    }

    function makeAction(item) {
      const classes = ["btn"];
      if (item.primary) classes.push("primary");
      if (item.danger) classes.push("danger");
      if (item.ghost) classes.push("ghost");
      const node = el("button", {
        class: classes.join(" "),
        type: "button",
        text: item.label || "",
      });
      if (item.disabled) node.disabled = true;
      node.addEventListener("click", function () {
        if (node.disabled) return;
        if (typeof item.onClick === "function") {
          const result = item.onClick(ctx);
          if (result === false) return;
        }
        if (item.keepOpen) return;
        ctx.close("value" in item ? item.value : true);
      });
      return node;
    }

    renderActions(config.actions || [{ label: T("common.ok"), value: true, primary: true }]);

    if (dismissible) {
      modal.addEventListener("mousedown", function (event) {
        if (event.target === modal) ctx.close(null);
      });
    }

    $("#modal-root").appendChild(modal);
    stack.push(ctx);

    if (typeof config.onMount === "function") {
      setTimeout(function () {
        config.onMount(ctx);
      }, 20);
    } else {
      const focusable = body.querySelector("input, textarea, select, .select");
      const primary = foot.querySelector(".btn.primary");
      setTimeout(function () {
        (focusable || primary || card).focus();
      }, 20);
    }

    return promise;
  }

  function closeAll() {
    stack.slice().forEach(function (ctx) {
      ctx.close(null);
    });
  }

  function confirm(options) {
    const config = options || {};
    return openModal({
      title: config.title || T("common.confirm"),
      subtitle: config.subtitle || "",
      size: "narrow",
      body: config.html || '<p>' + TP.esc(config.text || "") + "</p>",
      actions: [
        { label: config.cancel || T("common.cancel"), value: false, ghost: true },
        {
          label: config.ok || T("common.confirm"),
          value: true,
          primary: !config.danger,
          danger: !!config.danger,
        },
      ],
    }).then(function (value) {
      return value === true;
    });
  }

  function alert(options) {
    const config = options || {};
    return openModal({
      title: config.title || T("app.title"),
      size: "narrow",
      body: config.html || "<p>" + TP.esc(config.text || "") + "</p>",
      actions: [{ label: config.ok || T("common.ok"), value: true, primary: true }],
    });
  }

  /* ---------------------------------------------------------------- 下拉 */

  let openSelect = null;

  document.addEventListener("mousedown", function (event) {
    if (!openSelect) return;
    if (openSelect.node.contains(event.target)) return;
    openSelect.close();
  });

  /**
   * 自绘下拉。原生 <select> 的弹层在深色模式下没法控制，所以一律自绘。
   * @param {{options: Array<{value:string,label:string}>, value:string,
   *          onChange:(value:string)=>void, className?:string}} config
   */
  function select(config) {
    const node = el("div", { class: "select" + (config.className ? " " + config.className : ""), tabindex: "0" });
    const valueNode = el("span", { class: "select-value" });
    const arrow = el("span");
    arrow.innerHTML =
      '<svg class="select-arrow" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>';
    const menu = el("div", { class: "select-menu" });

    let current = config.value;
    const options = config.options || [];

    function labelOf(value) {
      const hit = options.find(function (item) {
        return String(item.value) === String(value);
      });
      return hit ? hit.label : options.length ? options[0].label : "";
    }

    function paint() {
      valueNode.textContent = labelOf(current);
      menu.innerHTML = "";
      options.forEach(function (item) {
        const option = el("button", {
          class: "select-option" + (String(item.value) === String(current) ? " active" : ""),
          type: "button",
          text: item.label,
        });
        option.addEventListener("click", function (event) {
          event.stopPropagation();
          current = item.value;
          paint();
          closeMenu();
          if (typeof config.onChange === "function") config.onChange(item.value);
        });
        menu.appendChild(option);
      });
    }

    function openMenu() {
      if (openSelect && openSelect.node !== node) openSelect.close();
      node.classList.add("open");
      openSelect = { node: node, close: closeMenu };
    }

    function closeMenu() {
      node.classList.remove("open");
      if (openSelect && openSelect.node === node) openSelect = null;
    }

    node.addEventListener("click", function (event) {
      event.stopPropagation();
      if (node.classList.contains("open")) closeMenu();
      else openMenu();
    });

    node.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (node.classList.contains("open")) closeMenu();
        else openMenu();
      }
    });

    node.appendChild(valueNode);
    node.appendChild(arrow);
    node.appendChild(menu);
    paint();

    node.setValue = function (value) {
      current = value;
      paint();
    };
    node.getValue = function () {
      return current;
    };
    return node;
  }

  /* ---------------------------------------------------------------- 开关 */

  function switchNode(config) {
    const label = el("label", { class: "switch" });
    const input = el("input", { type: "checkbox" });
    input.checked = !!config.checked;
    const track = el("span", { class: "switch-track" });
    label.appendChild(input);
    label.appendChild(track);
    input.addEventListener("change", function () {
      if (typeof config.onChange === "function") config.onChange(input.checked);
    });
    label.setChecked = function (value) {
      input.checked = !!value;
    };
    label.isChecked = function () {
      return input.checked;
    };
    return label;
  }

  /* ---------------------------------------------------------------- 导出 */

  TP.openModal = openModal;
  TP.closeAllModals = closeAll;
  TP.confirm = confirm;
  TP.alert = alert;
  TP.select = select;
  TP.switchNode = switchNode;
})(window.TP);
