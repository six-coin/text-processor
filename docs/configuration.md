# 配置与数据格式

本程序只有两个 JSON 文件：`app.json`（应用设置，数据目录根下）和 `project.json`（每个项目一份版本清单）。两者都是 UTF-8、无 BOM、4 空格缩进。

写入一律「临时文件 + `os.replace`」：中途崩溃不会留下半个文件。文件不存在时，第一次读取会用默认值写一份出来，用户不需要手写 JSON。

## 1. `app.json`

```json
{
    "language": "zh-CN",
    "theme": "light",
    "wrap": true,
    "display_limit": 10000,
    "font_size": 14.5,
    "doc_font": "default",
    "last_project": "project-a1b2",
    "recent": {
        "trim": {"params": {"chars": " \u3000\t"}, "compare": true}
    }
}
```

| 字段 | 类型 | 默认 | 取值与行为 |
|---|---|---|---|
| `language` | string | `""` | 语言包代号，对应 `app/locales/<代号>.json`。空串表示「按系统语言决定」；写盘时为空则删掉这个键，下次启动重新判断。不存在的代号回退到系统语言，再回退到第一个可用语言包。 |
| `theme` | string | `"light"` | `light` / `dark`。其它值（含 `system`）取当时的系统偏好；系统偏好读不到时用 `light`。 |
| `wrap` | bool | `true` | 正文是否自动换行。非布尔值按真假值处理；字符串 `"false"` 也算真。 |
| `display_limit` | int | `10000` | 正文一次最多显示多少字。`0` 或负数表示不限制；其它正整数按字面值使用（界面只提供 5,000 / 10,000 / 20,000 / 50,000 / 0 五档）。非数字回退 10000。只影响显示，处理始终用全文。 |
| `font_size` | number | `14.5` | 正文字号（像素）。超出 12–24 或不是数字都回退 14.5。行高 = 字号 × 1.8，一起缩放。 |
| `doc_font` | string | `"default"` | `default` / `simsun` / `simhei` / `kaiti` / `fangsong` / `dengxian`。认不出来的值回退 `default`。字体栈写在 `app/ui/web/js/core.js` 的 `TP.FONTS` 里。 |
| `last_project` | string | `""` | 上次打开的项目 ID。指向不存在的项目时静默忽略并清空，不会弹错。 |
| `recent` | object | `{}` | 处理器 ID → `{"params": {...}, "compare": bool}`，记住上次填的参数。超过 40 条时丢最旧的。 |

未知键原样保留：读进来什么样，写回去还是什么样，方便将来加字段时旧版本不丢数据。

## 2. `project.json`

```json
{
    "schema": 1,
    "id": "project-a1b2",
    "name": "红楼梦校订",
    "created": "2026-11-16 18:44",
    "updated": "2026-11-16 19:02",
    "versions": [
        {
            "index": 1,
            "title": "原始文本",
            "kind": "origin",
            "at": "2026-11-16 18:44",
            "lines": 120,
            "chars": 3120
        }
    ]
}
```

| 字段 | 类型 | 默认 | 取值与行为 |
|---|---|---|---|
| `schema` | int | `1` | 结构版本号。目前只写不读，留给以后迁移。 |
| `id` | string | 文件夹名 | 与文件夹同名。清单里的值和文件夹对不上时以清单为准。 |
| `name` | string | 文件夹名 | 显示名。新建时最长 40 字，超出截断；空名拒绝创建。 |
| `created` | string | `""` | `YYYY-MM-DD HH:MM`。 |
| `updated` | string | 最后一版的时间 | 每次追加版本时更新。列表按它倒序。 |
| `versions[]` | array | 至少一项 | 空数组或缺失视为项目损坏，列表里标「无法读取」。 |
| `versions[].index` | int | — | 从 1 开始，必须连续；读的时候按它排序。 |
| `versions[].title` | string | `第 N 版` | 给人看的标题。处理器被删掉也不影响历史可读。 |
| `versions[].kind` | string | `processor` | `origin`（初始文本）/ `processor`（处理器生成）/ `manual`（手动修改）。 |
| `versions[].at` | string | `""` | 生成时间，`YYYY-MM-DD HH:MM`。 |
| `versions[].lines` / `chars` | int | `0` | 该版本的统计，写版本时算一次。 |

正文存在 `versions/0001.txt`、`0002.txt`…… 文件名是四位序号，与 `index` 对应。清单里有、文件不在的版本在读取时会被跳过，不会崩。

## 3. 校验时机

| 时机 | 检查什么 | 越界怎么办 |
|---|---|---|
| 读 `app.json` | 每个键的类型与取值 | 逐键夹取或回退默认值，未知键保留 |
| 读 `project.json` | 顶层是对象、`versions` 非空 | 抛 `ProjectError`，项目标成「无法读取」 |
| 保存处理器前 | 语法、导入白名单、`init()` 字段、`process()` 签名 | 抛 `ProcessorError`，**不落盘** |
| 启动时 | 数据目录搬迁标记、目录是否存在 | 搬迁失败写日志，旧数据留在原处 |

配置 JSON 本身语法错（比如多了个逗号）不夹取，直接抛 `ConfigError` 并走崩溃弹窗——半个合法的配置比没有更危险。

## 4. 语言包

- 位置：`app/locales/<语言代码>.json`，文件名就是语言代码（`zh-CN`、`en-US`）。
- 结构：扁平键值对，值为字符串。`language.name` 是语言自己的名字，显示在设置里。
- 占位符：`{name}` 形式，查表时用 `format(**values)` 填。填不上就原样保留，不抛异常。
- 回退顺序：当前语言 → `en-US` → 键名本身。
- 新增一种语言 = 放一个新文件，不需要改代码。扫描按文件名字典序，界面里就是这个顺序。

键的命名是「区域.对象.属性」，例如 `doc.preview.confirm.title`。`type.*` 与 `font.*` 是拼出来的（`T("type." + kind)`），不是独立的键名。

## 5. 日志

| 项 | 值 |
|---|---|
| 位置 | `%LOCALAPPDATA%\six-coin\text-processor\logs\` |
| 文件名 | `main_YYYY-MM-DD_HH-MM-SS.log`，每次启动一个 |
| 格式 | `[LEVEL] [YYYY-MM-DD HH:mm:ss] 消息` |
| 轮转 | 单文件超过 5 MB 换新文件 |
| 保留 | 14 天 |

崩溃弹窗统一三段：出了什么事、发生时间、日志在哪。日志默认不打印局部变量（`diagnose=False`），避免把敏感内容写进文件。
