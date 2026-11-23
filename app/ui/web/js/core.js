/* 核心：命名空间、状态、桥接、文案、轻提示、动效工具。
   所有文件都是普通脚本（不是 ES 模块），按 index.html 里的顺序加载，
   各自往 window.TP 上挂东西。 */

window.TP = window.TP || {};

(function (TP) {
  "use strict";

  /* ---------------------------------------------------------------- 状态 */

  //: 最近一次快照，只读。任何界面都从这里取数据。
  TP.state = null;
  //: 当前语言的键表。
  TP.strings = {};
  //: 界面自己的临时状态，不来自后端。
  TP.ui = {
    view: "main",
    railTab: "ops",
    projectQuery: "",
    processorId: "",
    processorDraft: null,
    dirty: false,
    settingsTab: "general",
    find: { open: false, query: "", hits: [], index: 0 },
    lastVersionCount: 0,
    lastProjectId: "",
  };

  /* ---------------------------------------------------------------- DOM */

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $$(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** 生成元素：el("div", {class: "x", onclick: fn}, "<b>hi</b>") */
  function el(tag, attrs, html) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        const value = attrs[key];
        if (value == null || value === false) return;
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key === "html") node.innerHTML = value;
        else if (key.slice(0, 2) === "on" && typeof value === "function") {
          node.addEventListener(key.slice(2), value);
        } else if (key === "dataset") {
          Object.keys(value).forEach(function (name) {
            node.dataset[name] = value[name];
          });
        } else {
          node.setAttribute(key, value);
        }
      });
    }
    if (html != null) node.innerHTML = html;
    return node;
  }

  /* ---------------------------------------------------------------- 文案 */

  function T(key, vars) {
    let text = TP.strings[key];
    if (text == null) text = key;
    if (!vars) return text;
    return String(text).replace(/\{(\w+)\}/g, function (match, name) {
      return Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match;
    });
  }

  function applyStrings() {
    $$("[data-i18n]").forEach(function (node) {
      const key = node.dataset.i18n;
      const vars = node.dataset.n != null ? { n: node.dataset.n } : null;
      node.textContent = T(key, vars);
    });
    $$("[data-i18n-title]").forEach(function (node) {
      node.setAttribute("title", T(node.dataset.i18nTitle));
    });
    $$("[data-i18n-placeholder]").forEach(function (node) {
      node.setAttribute("placeholder", T(node.dataset.i18nPlaceholder));
    });
    document.documentElement.setAttribute("lang", TP.state && TP.state.language ? TP.state.language : "zh-CN");
  }

  /* ---------------------------------------------------------------- 桥接 */

  async function call(method) {
    const args = Array.prototype.slice.call(arguments, 1);
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api[method] !== "function") {
      toast(T("error.generic", { error: "后端未就绪" }), true);
      return null;
    }
    try {
      const result = await api[method].apply(api, args);
      return result || null;
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      toast(T("error.generic", { error: message }), true);
      return null;
    }
  }

  /* ---------------------------------------------------------------- 状态栏 */
  /* 底部居中的圆角黑条，界面上唯一的临时提示出口。容器底边固定、条目往上堆，
     所以新的一条从下面出来时，已有的会自己上移一格；最多同时三条。 */

  /** 记下每条现在的位置，等 DOM 改完再按位移补动画。 */
  function toastSnapshot(root) {
    const map = new Map();
    for (const node of root.children) map.set(node, node.getBoundingClientRect().top);
    return map;
  }

  /** 把「被顶上去」的位移反向补回来再归零：看起来是往上挪了一格，而不是跳一格。 */
  function toastSettle(map) {
    map.forEach(function (top, node) {
      if (!node.isConnected) return;
      const delta = top - node.getBoundingClientRect().top;
      if (!delta) return;
      node.style.transition = "none";
      node.style.transform = "translateY(" + delta + "px)";
      // 强制回流：否则下一帧的 transition 会从同一个值开始，等于没动。
      void node.offsetHeight;
      node.style.transition = "transform 0.2s var(--ease)";
      node.style.transform = "";
    });
  }

  /** 让一条原地脱离文档流再飘走，后面的条目不会跟着往下掉。 */
  function toastRetire(node) {
    if (!node.isConnected) return;
    const rect = node.getBoundingClientRect();
    const ghost = node.cloneNode(true);
    ghost.classList.remove("is-entering", "is-leaving");
    ghost.style.position = "fixed";
    ghost.style.left = rect.left + "px";
    ghost.style.top = rect.top + "px";
    // 量出来的宽高要写死：离开容器后它是一块普通的 div，会撑满整行。
    ghost.style.width = rect.width + "px";
    ghost.style.height = rect.height + "px";
    ghost.style.margin = "0";
    ghost.style.pointerEvents = "none";
    ghost.style.animation = "toast-out 0.2s ease forwards";
    document.body.appendChild(ghost);
    setTimeout(function () {
      ghost.remove();
    }, 240);
    node.remove();
  }

  function toastDismiss(node) {
    if (!node.isConnected || node.classList.contains("is-leaving")) return;
    const map = toastSnapshot(node.parentElement);
    toastRetire(node);
    toastSettle(map);
  }

  /** 弹一条状态。``isError`` 为真时是错误样式，停留更久。 */
  function toast(message, isError) {
    const root = $("#toast-root");
    const text = String(message === undefined || message === null ? "" : message).trim();
    if (!root || !text) return;

    const map = toastSnapshot(root);
    while (root.children.length >= 3) toastRetire(root.firstElementChild);

    const node = el("div", { class: "toast" + (isError ? " is-error" : ""), text: text });
    node.classList.add("is-entering");
    root.appendChild(node);
    toastSettle(map);

    setTimeout(function () {
      toastDismiss(node);
    }, isError ? 4200 : 2600);
  }

  /* ---------------------------------------------------------------- 动效 */

  /**
   * 重新播放一次「只播一次」的动画类。
   * 每个类名各自一个计时器，避免两段动画互相 clearTimeout。
   */
  function replay(node, className, duration) {
    if (!node) return;
    if (!node.__timers) node.__timers = {};
    node.classList.remove(className);
    // 强制 reflow，否则移除和添加在同一帧里，动画不会重新触发。
    void node.offsetWidth;
    node.classList.add(className);
    clearTimeout(node.__timers[className]);
    node.__timers[className] = setTimeout(function () {
      node.classList.remove(className);
    }, duration || 400);
  }

  const VIEW_ANIM = 260;

  function switchView(name) {
    const next = $('.view[data-view="' + name + '"]');
    if (!next) return;
    const current = $(".view.is-active");
    const changed = TP.ui.view !== name;
    TP.ui.view = name;
    if (current === next) return;
    if (current) current.classList.remove("is-active");
    next.classList.add("is-active");
    if (changed) replay(next, "is-entering", VIEW_ANIM);
    const focusable = next.querySelector("input, textarea, .btn.primary");
    if (focusable && name !== "main") setTimeout(function () { focusable.focus(); }, 40);
  }

  function setTheme(theme) {
    const value = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = value;
    try {
      localStorage.setItem("tp-theme", value);
    } catch (error) {
      /* 存不住就算了，下次启动按配置来 */
    }
  }

  /* ---------------------------------------------------------------- 格式化 */

  function shortTime(text) {
    const value = String(text || "");
    // 2026-11-16 19:02 → 11-16 19:02
    return /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(5) : value;
  }

  function number(value) {
    const language = (TP.state && TP.state.language) || "zh-CN";
    return Number(value || 0).toLocaleString(language);
  }

  /** 输入防抖：用于搜索框这类每敲一下就重绘的地方。 */
  function debounce(fn, wait) {
    let timer = null;
    return function () {
      const args = arguments;
      const self = this;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(self, args);
      }, wait);
    };
  }

  /* ---------------------------------------------------------------- 导出 */

  TP.$ = $;
  TP.$$ = $$;
  TP.el = el;
  TP.esc = esc;
  TP.T = T;
  TP.call = call;
  TP.toast = toast;
  TP.replay = replay;
  TP.switchView = switchView;
  TP.setTheme = setTheme;
  TP.applyStrings = applyStrings;
  TP.shortTime = shortTime;
  TP.number = number;
  TP.debounce = debounce;

  TP.current = function () {
    return TP.state && TP.state.current ? TP.state.current : null;
  };

  TP.hasProject = function () {
    return !!(TP.state && TP.state.current);
  };

  TP.inPreview = function () {
    return !!(TP.state && TP.state.preview);
  };

  TP.processorById = function (id) {
    if (!TP.state) return null;
    return TP.state.processors.find(function (item) {
      return item.id === id;
    }) || null;
  };

  TP.typeLabel = function (type) {
    return T("type." + type);
  };

  //: 正文可选的字体栈。键要和 settings.DOC_FONTS 一致。
  TP.FONTS = {
    default: '"Microsoft YaHei", "Segoe UI", "Helvetica Neue", sans-serif',
    simsun: 'SimSun, "Songti SC", "STSong", serif',
    simhei: 'SimHei, "Heiti SC", "STHeiti", sans-serif',
    kaiti: 'KaiTi, "Kaiti SC", "STKaiti", serif',
    fangsong: 'FangSong, "FangSong_GB2312", "STFangsong", serif',
    dengxian: '"DengXian", "Microsoft YaHei", sans-serif',
  };
  TP.FONT_KEYS = ["default", "simsun", "simhei", "kaiti", "fangsong", "dengxian"];
})(window.TP);
