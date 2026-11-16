# 扩展指南

按「我要加一个 X」组织。每节给具体文件路径与片段，照着改完跑第 6 节的清单。

## 1. 新增一个设置项

以「加一个『正文最大宽度』」为例。

### 1.1 `app/settings.py`

三处：默认值、读盘夹取、对外快照。

```python
_DEFAULT: dict[str, Any] = {
    ...
    "doc_width": 0,          # 0 表示不限
}

def coerce_doc_width(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

    # _normalize 里
    data["doc_width"] = coerce_doc_width(raw.get("doc_width"))

    # as_dict 里
    "doc_width": int(self._data.get("doc_width", 0)),
```

### 1.2 `app/ui/api.py`

快照加字段，`update_settings` 加分支：

```python
"doc_width": int(self._settings.get("doc_width", 0)),

if "doc_width" in patch:
    self._settings.set("doc_width", settings.coerce_doc_width(patch["doc_width"]))
```

### 1.3 `app/ui/web/js/view-settings.js`

在 `openSettings()` 里插一行，位置按「先看后改」的顺序放：

```javascript
list.appendChild(
  row(
    T("settings.width"),
    T("settings.width.desc"),
    TP.select({
      options: [0, 720, 860, 1040].map(function (value) {
        return { value: String(value), label: value ? value + " px" : T("settings.display.none") };
      }),
      value: String(state.doc_width || 0),
      onChange: function (value) {
        call("update_settings", { doc_width: Number(value) }).then(function (snapshot) {
          if (snapshot) TP.apply(snapshot);
        });
      },
    })
  )
);
```

### 1.4 `app/ui/web/js/main.js`

如果设置项影响样式，在 `apply()` 里写成 CSS 变量：

```javascript
if (snapshot.doc_width != null) {
  document.documentElement.style.setProperty("--doc-width", snapshot.doc_width + "px");
}
```

样式侧在 `app/ui/web/css/tokens.css` 给一个默认值，`views.css` 里消费它。

### 1.5 文案与文档

- `app/locales/zh-CN.json` 与 `app/locales/en-US.json` **两份都要加**，键必须一一对应。
- `docs/configuration.md` 的字段表补一行。
- `docs/readme/zh-CN.md` 与 `en-US.md` 的「设置」表补一行，两份同序。

## 2. 新增一种处理器参数类型

以「加一个 `path` 类型（界面上给一个文件选择器）」为例。

### 2.1 `app/core/processors.py`

```python
_TYPE_ALIASES = {
    ...
    "path": "path",
}

def _coerce(arg_type: str, value: Any, label: str) -> Any:
    if arg_type == "path":
        return str(value or "").strip()
    ...
```

### 2.2 `app/ui/web/js/overlays.js`

`runProcessor()` 里加一个分支，并在提交时按类型取值：

```javascript
if (arg.type === "path") {
  // 渲染一个输入框 + 「浏览」按钮，按钮调 call("browse_folder")
}
```

### 2.3 `app/core/prompt.py`

提示词里的类型列表要跟着加，否则 AI 永远写不出这种参数：

```
| str / text / int / float / bool / choice / path |
```

### 2.4 测试

`tests/test_processors.py` 加一个用例，确认默认值能正确转换、越界值被夹取。

## 3. 新增一种界面语言

1. 复制 `app/locales/en-US.json` 为 `app/locales/<新代码>.json`（例如 `ja-JP.json`）。
2. 逐条翻译，`language.name` 写成这门语言自己的名字（例如 `日本語`）。
3. 什么都不用改：`i18n.available()` 扫目录，设置里的下拉框自动多一项。
4. 跑 `pytest tests/test_i18n.py`：键必须与中文版完全一致，占位符必须一致，不能残留中文。

注意：`docs/readme/` 只出中英两份，不要为新语言补手册——手册多一份就多一份要同步的正文。

## 4. 新增一个内置处理器

1. 在 `app/resources/processors/` 新建一个 `.py`，按 `docs/architecture.md` 的契约写 `init()` 与 `process()`。
2. 文件名（去扩展名）就是它的身份，**不要与已有的重名**。
3. 跑 `pytest tests/test_processors.py`：所有内置处理器必须能加载。

新装用户首次启动就会铺上；已经装过的用户需要点一次处理器页的「恢复内置处理器」——`seed_builtins()` 只在处理器目录为空时铺，`restore_builtins()` 才补缺的那几个。

内置处理器是只读的，用户改不了也删不掉，所以新增内置逻辑要谨慎：一旦发出去，就只能靠新文件名替换。

## 5. 新增一个 `js_api` 方法

1. `app/ui/api.py` 里加方法，**返回完整快照**（`self._snapshot(...)` 或 `self._with_text(...)`），不要返回裸数据。
2. 失败用 `self._fail(消息)`，不要抛异常给前端。
3. 前端统一走 `TP.call("方法名", ...)`，它会处理桥接异常并弹提示。
4. 需要原生对话框时用 `self._pick(webview.OPEN_DIALOG, ...)`，它已经处理了「窗口未就绪」和「用户取消」。

## 6. 提交前检查清单

- [ ] 中英两份语言包的键与占位符都改了（`pytest tests/test_i18n.py`）
- [ ] 新增的设置项写进了 `docs/configuration.md` 的字段表，并写清越界行为
- [ ] 界面变了就改 `docs/readme/` 两份手册的「界面」或「设置」表，两份同序
- [ ] 处理器契约变了，`app/core/prompt.py` 同步改了
- [ ] 内置处理器变了，`app/resources/processors/` 里的是最终版本
- [ ] 新增测试，或说明了为什么不加
- [ ] `pyproject.toml` 的 `description` 仍与 `docs/readme/en-US.md` 第二行逐字相同

```bat
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
