# Text Processor User Manual

Turn long documents into a chain of reviewable versions with small Python scripts.

[简体中文](zh-CN.md)

---

## 1. Installation

You need Windows 10/11, [uv](https://docs.astral.sh/uv/), and the WebView2 Runtime (built into Windows 11; on Windows 10 it usually arrives with Edge).

```bat
setup.bat
```

It runs `uv sync` and installs the dependencies into `.venv` next to the program. To move to another machine, copy the whole folder and run `setup.bat` again.

## 2. Starting

| File | Purpose |
|---|---|
| `main.bat` | Everyday start, no console window |
| `main.pyw` | Same thing; double-clicking it works too |

Only one window is allowed. Starting the program again does not open a second window; it brings the existing one to the front.

## 3. The window

The window has three columns:

| Area | Contents |
|---|---|
| Left | Project list and search; "New project" at the bottom |
| Middle | The current version, read-only; the header carries title, version, time, size and tools |
| Right | "Actions" and "History" tabs; the bottom button opens the processors page |

Below 1120 pixels wide the right column collapses into a drawer; open it with the button at the top right of the text pane.

## 4. Projects

- **New**: click "New project" (or press `Ctrl+N`). Name it, paste the text into "Initial text", or click "Import .txt" and pick a file.
- **Import**: reads UTF-8, GBK/GB18030 and UTF-16 with a BOM. There is no extra size limit.
- **Search**: filters the list by name, case-insensitive.
- **Delete**: hover a project row and click the bin icon that appears. The project moves to the recycle folder instead of vanishing.

## 5. Versions

Every operation appends a new version. Older versions stay exactly as they were.

| Action | Result |
|---|---|
| Run a processor | Appends a version titled with the processor name |
| Edit manually | Appends a version titled "Edit manually" |
| Click a version under "History" | The text switches to a read-only preview and a banner appears |
| "Continue from here" | Deletes every version after that one and makes it current |

"Continue from here" really deletes the later versions; the confirmation says how many and that it cannot be undone. While previewing you cannot run processors or edit manually.

## 6. Processors

A processor is a small script that turns text into new text. Five are built in: trim each line, remove blank lines, find and replace, check line endings, check line length.

To run one: click it under "Actions" in the right column, fill in the parameters, confirm.

| Type | What it does |
|---|---|
| Per line | Works one line at a time; the line count does not change |
| Whole text | Gets the entire text and may add or remove lines |
| Check | Changes nothing; lists the lines that need attention and why |

Per-line processors can turn on "Review changes line by line": the changes are listed in a table with one switch per line, and you decide which ones apply.

## 7. Editing manually

"Edit manually" at the top right of the text pane opens an editor.

| Button | Effect |
|---|---|
| Save | Creates a new version |
| Open in external editor | Writes the current text to a temporary file and opens it in your default editor; the text area here becomes read-only |
| Reload | Reads back whatever the external editor saved |

You can also edit externally and click "Save" directly — it re-reads the file before saving, so you do not have to click "Reload" first.

## 8. Writing a processor with AI

Processors page → "Write with AI":

1. Describe the effect you want in one sentence.
2. Click "Copy prompt". The whole prompt (interface description plus three examples) goes to the clipboard.
3. Paste it into any web-based AI chat and take the code it returns.
4. Paste that code back into the box and click "Check and save".

Nothing is saved unless it validates, and errors point at the line number. The prompt already contains the full interface contract, so the AI never needs to see this program's code.

## 9. The processors page

The left column lists every processor by type; built-in ones carry a "Built-in" badge. The right column is the source editor.

| Button | Effect |
|---|---|
| Check | Validates without saving |
| Save | Writes the file after validation; otherwise reports why |
| Delete | Removes the processor; versions it already produced are unaffected |

Built-in processors are read-only: the code cannot be edited and there is no delete button. To change built-in behaviour, create a new processor with "Write code" or "Write with AI".

## 10. Find

`Ctrl+F` opens the find bar. Typing highlights matches, `Enter` jumps to the next one, `Shift+Enter` to the previous one. Find only covers the text that is currently displayed.

## 11. Keyboard shortcuts

| Key | Effect |
|---|---|
| `Ctrl+N` | New project |
| `Ctrl+F` | Open find |
| `Esc` | Close the find bar or a dialog |
| `Enter` | Next match in the find bar |
| `Shift+Enter` | Previous match in the find bar |
| `Ctrl+S` | Save in the processor editor |

## 12. Settings

Click the gear at the top left. Settings live in `app.json` and apply immediately.

| Setting | Values | Notes |
|---|---|---|
| Interface language | 简体中文 / English | Switches at once and is remembered |
| Theme | Light / Dark | Applies immediately |
| Word wrap | On / Off | When off, lines do not wrap and line numbers appear |
| Body font | Microsoft YaHei / SimSun / SimHei / KaiTi / FangSong / DengXian | Preview only |
| Body font size | 13 / 14.5 / 16 / 18 / 20 | Preview only |
| Preview limit | 5,000 / 10,000 / 20,000 / 50,000 / No limit | The rest is not shown; processing still uses the full text |
| Data directory | Any absolute path | Moves on the next start; you can restart right away |
| Recycle folder | — | Opens the folder holding deleted projects |

## 13. Files and folders

```
<program folder>              code and bundled resources
<data folder>                 %PROGRAMDATA%\six-coin\text-processor
├─ app.json                   settings
├─ projects\                  one folder per project
│  └─ <project>\
│     ├─ project.json         version manifest
│     └─ versions\            0001.txt, 0002.txt, ...
├─ processors\                processor scripts
└─ recycle\                   deleted projects
<local folder>                %LOCALAPPDATA%\six-coin\text-processor
└─ logs\                      one file per run, kept for 14 days
<temp folder>                 %TEMP%\six-coin\text-processor
```

- `projects`, `processors` and `app.json` are not tracked by version control.
- Deleting `<data folder>` is a factory reset: every project and every custom processor is gone.
- Log files rotate at 5 MB and are kept for at most 14 days.

## 14. Troubleshooting

**`main.bat` closes instantly.** Dependencies are missing. Run `setup.bat` first; it reports what is missing.

**"The program is already running".** Only one window is allowed. Find the existing one on the taskbar.

**Only part of the text is shown.** The preview limit is doing its job. It affects display only — processing still uses the full text. Choose "No limit" to see everything.

**I changed the data directory but nothing moved after restarting.** Moving happens once, at startup. If the target is not writable it is skipped, the old data stays, and the log records it.

**A processor will not save.** Read the message: usually `init()` is missing a field, or the parameters of `process()` do not match `args`.

**A processor fails at runtime.** The error carries a line number. Use "Check" to find syntax problems first, then review line by line.

## 15. Known limitations

- Windows only.
- The text is read-only; every change must become a version, so you cannot edit while reading.
- Processors run inside the app process with no sandbox. Only network imports, subprocesses and file writes are blocked.
- Find only covers the text that is displayed, which the preview limit may cut short.
- There is no export; take `versions\NNNN.txt` from the data folder when you need one.
- One window and one open project at a time.

## 16. Development

See [`architecture.md`](../architecture.md) for layering, module boundaries and the rules that must not break; [`configuration.md`](../configuration.md) for every configuration field; [`extending.md`](../extending.md) for where to touch when adding something.

```bat
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
