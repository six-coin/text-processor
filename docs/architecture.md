# 架构

本项目遵循 `reference.md`。本文只写这个项目自己的分层、数据模型与不能破的约定。

## 1. 目标与约束

把长文档放进「项目」，用一个个小 Python 脚本（处理器）逐版加工，每一版都留痕、可回看、可回退。单机、无服务端、双击即用。

| 约束 | 谁在守 |
|---|---|
| 依赖只用 uv 管理，虚拟环境只在项目根 | `tests/test_source_hygiene.py::test_pyproject_declares_runtime_deps` |
| 数据目录、本地目录、临时目录分开 | `app/paths.py`（导入时定死）、`tests/test_paths.py` |
| 界面文案只走语言包，键不能多也不能少 | `tests/test_i18n.py::test_every_used_key_exists`、`::test_no_unused_keys_left_behind` |
| 中英两份语言包的键与占位符必须一致 | `tests/test_i18n.py::test_locales_have_the_same_keys` |
| 处理器契约与 AI 提示词是同一套 | `app/core/prompt.py` 与 `app/core/processors.py` 同改 |
| 内置处理器只读 | `tests/test_processors.py::test_builtin_cannot_be_deleted` |
| 正文只在变化时下发 | `app/ui/api.py::_snapshot` |
| 前端不引入构建步骤 | `app/ui/web/index.html` 按顺序加载普通脚本 |

## 2. 目录结构

```
main.pyw                入口薄壳，只调 app.ui.app.main()
app/
├─ paths.py             四类目录的唯一来源
├─ settings.py          app.json 读写与夹取
├─ i18n.py              语言包扫描与查表
├─ logging_setup.py     日志、崩溃弹窗
├─ bootstrap.py         建目录、铺内置处理器
├─ errors.py            异常体系
├─ version.py           版本号（来自 pyproject.toml）
├─ core/                业务逻辑，不碰界面
│  ├─ processors.py     处理器加载、校验、执行
│  ├─ projects.py       项目与版本链
│  ├─ diff.py           行内差异片段
│  ├─ review.py         待确认改动的内存表
│  ├─ prompt.py         给网页端 AI 的提示词
│  └─ text.py           行切分、统计、容错解码
├─ system/              与操作系统打交道
│  ├─ single.py         单实例互斥量
│  ├─ theme.py          浅色 / 深色
│  └─ shell.py          剪贴板、打开文件与目录
├─ resources/processors/ 内置处理器的源文件（只读，首次启动铺到数据目录）
├─ locales/             语言包
└─ ui/
   ├─ api.py            唯一的前后端通道
   ├─ app.py            窗口装配与启动
   └─ web/              index.html + css/ + js/
tests/                  见第 11 节
docs/                   本目录
```

## 3. 分层与依赖方向

```
ui/api.py ──► core/* ──► paths / errors
   │            │
   │            └────► settings / i18n（只读配置与文案）
   └──► system/*
```

规则：

- **core 不 import webview**，也不读 `ui/`。`tests/test_source_hygiene.py::test_app_does_not_import_webview_in_core` 守着。
- **paths 只回答「路径在哪」**，不判断文件存在、不读写业务数据。
- **ui 层可以依赖任何一层**，反向不行。
- 前端只认 `app/ui/api.py` 的公开方法，不自己拼路径、不自己算业务规则。

## 4. 数据模型

### 项目与版本

一个项目是一个文件夹，里面两份东西：`project.json`（清单）和 `versions/0001.txt`（正文）。

**版本只追加，不原地改。** 「回到旧版本」= 截断到那一版，后面的版本文件真的删掉。这样做的原因：一个版本就是一份完整快照，回看时不需要重放历史；代价是磁盘占用随版本数线性增长，对纯文本可以接受。

**版本标题存在清单里，不存在文件名里。** 文件名只是序号（`0002.txt`），标题是「去除首尾空白」这种给人看的字符串。原因：处理器可能被删掉，而历史必须一直读得懂。

### 处理器

一个处理器是一个 `.py` 文件，文件名（去掉扩展名）就是它的身份，界面上从不显示。原因：用户不需要知道内部标识；换个名字显示（`init()["name"]`）就能改称呼，不必动文件。

内置处理器的判定是「文件名出现在 `app/resources/processors/` 里」，不靠额外标记。原因：判定标准单一，复制一份改个名就自动变成用户处理器。

## 5. 模块职责

| 模块 | 只做什么 | 不做什么 |
|---|---|---|
| `paths` | 算出四类目录、处理数据目录搬迁 | 不建目录、不读写数据 |
| `settings` | 读写 `app.json`、夹取非法值 | 不管界面状态 |
| `i18n` | 扫描语言包、查表、填占位符 | 不格式化数字、不拼句子 |
| `core/processors` | 加载、静态检查、执行处理器 | 不决定界面怎么显示参数 |
| `core/projects` | 版本链的增删查、旧项目迁移 | 不判断「能不能删」（由 api 判） |
| `core/diff` | 输出片段数组 | 不生成 HTML |
| `core/review` | 暂存待确认改动 | 不落盘 |
| `core/prompt` | 拼 AI 提示词 | 不调 AI |
| `ui/api` | 快照、权限判断、错误转文案 | 不做业务计算 |
| `ui/app` | 窗口、单实例、关闭握手、重启 | 不碰业务 |

## 6. 关键流程

### 运行处理器

```
界面 → api.apply_processor → processors.coerce_args → processors.apply
     → 需要确认？ review.Store.put → 返回 review 负载 → 界面弹评审
     → 不需要确认？ projects.append → 返回快照（含新正文）
```

需要确认时**不落盘**：结果只在内存里等用户逐行决定。原因：一次误操作不该留下一个半成品版本。

### 版本截断

```
api.continue_from → projects.truncate（删 versions/NNNN.txt 与清单条目）→ 返回该版正文
```

先删文件再改清单：清单是唯一真相，清单里还有但文件没了的版本会被 `_build` 跳过。

### 关闭握手

```
窗口 closing 事件 → api.allow_close()
  ├─ 没有未保存改动 → 放行
  └─ 有 → 返回 False，另起线程让页面弹确认框
        → 用户选「放弃并关闭」→ api.answer_close → window.destroy()
```

`dirty` 由处理器编辑器在脏状态**变化时**同步（不是每次按键），避免每敲一个字都过一趟 IPC。

### 数据目录搬迁

```
设置里点「更改」→ api.set_data_dir → paths.request_data_dir（只写 pending 标记）
→ 下次启动：paths 在 import 时读标记 → 搬内容 → 改指针 → 清标记
```

搬迁放在 `paths` 的 import 阶段，因为 `DATA_DIR` 是模块级常量，晚一步就改不动了。

## 7. 前后端契约

每个 `js_api` 方法都返回**完整快照**，外加 `ok` 与 `message`。前端拿到就整体重绘，不维护第二份状态。

| 字段 | 说明 |
|---|---|
| `ok` | 这次操作有没有生效；False 时前端额外弹一条错误提示 |
| `message` | 给人看的一句话，成功失败都可能有 |
| `projects` / `current` / `versions` | 项目与版本链 |
| `preview` | 非空表示正在预览旧版本 |
| `text` | **只在正文变化时出现**；没有就沿用上一份 |
| `text_meta` | 全文与已显示部分的统计（`chars` / `lines` / `shown_chars` / `shown_lines` / `truncated`） |
| `processors` | 含源码与上次用过的参数 |
| `review` | 非空表示这次操作需要逐行确认 |
| `display_limit` / `font_size` / `doc_font` / `wrap` / `theme` | 界面偏好 |

正文单独处理的原因：一篇几十万字的文本每次都随快照下发，会让每次点击都卡一下。

非法参数一律**夹取**而不是报错：数字越界夹到边界，认不出来的枚举回退默认值。只有真正无法继续的情况（项目不存在、处理器语法错）才返回 `ok: False`。

## 8. 线程模型

| 线程 | 归属 | 做什么 |
|---|---|---|
| GUI 线程 | pywebview | 窗口、原生对话框、`window.destroy()` |
| js_api 线程 | pywebview 每调用一个 | 执行 `Api` 的方法 |
| 关闭确认线程 | `app.py` 临时起 | 调 `evaluate_js` 请页面弹框 |

跨线程只传数据，不传对象引用。`Api` 的每个方法都在 `self._lock` 里执行，因为两次调用可能真的同时进来。

## 9. 错误处理

| 场景 | 策略 |
|---|---|
| 单个处理器文件不合法 | 记日志、进 `processor_errors`，其余照常加载 |
| 项目清单损坏 | 项目列表里标「无法读取」，点它只提示原因，不崩 |
| 配置 JSON 损坏 | 抛 `ConfigError`，启动时走崩溃弹窗 |
| 处理器运行时抛异常 | 包装成 `ProcessorError`，带行号，返回 `ok: False` |
| 未预料的异常 | `logging_setup` 的 excepthook 兜底，弹窗后退出 |

原则：**能局部失败的绝不整体失败**。一个坏处理器不该让整个列表消失。

## 10. 配置与本地化

- 配置键与默认值见 [`configuration.md`](configuration.md)。
- 语言包按文件名识别语言，`available()` 扫目录得到列表，加一种语言就是加一个文件。
- 缺键先回退 `en-US`，再缺就返回键名本身，永远不抛异常。
- 界面里所有可见文案都来自语言包；`core/processors.py` 与 `core/projects.py` 里的错误文案是硬编码中文，因为它们描述的是脚本本身的问题，属于开发者视角。

## 11. 测试策略

```
tests/
├─ conftest.py            把三类目录指到临时位置，每个用例清空项目与处理器
├─ test_paths.py          目录解析、指针读写
├─ test_settings.py       默认值、未知键保留、损坏、夹取
├─ test_i18n.py           键覆盖、占位符、中英一致、无中文残留
├─ test_processors.py     契约校验、执行、内置只读
├─ test_projects.py       版本链、截断、迁移、回收站
├─ test_text.py           行切分、统计、编码兜底
├─ test_prompt.py         提示词自包含
├─ test_ui_wiring.py      JS 引用的 id 存在、样式表与脚本齐全、无调试残留
└─ test_source_hygiene.py 依赖、锁文件、入口薄壳、core 不碰 webview
```

夹具约定：`conftest.py` 在导入 `app` **之前**设置 `SIXCOIN_DATA_DIR` 等环境变量，因为 `paths` 在 import 时就定死了 `DATA_DIR`。每个用例前后清空 `projects`、`processors`、`recycle`。

界面层的验证不在 pytest 里：用真实 `Api` + 本地 HTTP + 浏览器跑截图与盒模型审计，见第 12 节最后一条。

## 12. 不能破的约定

1. **core 不 import webview**，也不读 `ui/`。
2. **`DATA_DIR` 在 import 时确定**；要换目录只能走 pending 标记，不能中途改常量。
3. **正文只在变化时下发**，`text` 字段缺席意味着沿用上一份。
4. **版本只追加**；截断是唯一的删除途径，且必须由用户确认。
5. **处理器文件名是身份，界面不显示它**；历史里存的是标题。
6. **内置处理器只读**，恢复靠 `restore_builtins()`。
7. **所有可见文案走语言包**，中英两份键必须一一对应。
8. **前端不引入构建步骤**：普通 `<script>` 按顺序加载，共用 `window.TP`。
9. **写配置一律临时文件 + `os.replace`**，中途崩溃不留半个文件。
10. **能局部失败的绝不整体失败**：坏处理器、坏项目都只影响自己。
11. **动画写在基础规则上**，不要只写在 `:focus` / `:hover` 里，否则退出时是瞬变。
12. **重绘不能打断动画**：先乐观更新 DOM，接口成功后只更新内存；必须重绘时等过渡结束。
