# ruff: noqa: E501
"""给网页端 AI 的提示词。

用户在界面上用一句自然语言说清「想要什么效果」，这里把它和完整的接口说明拼成
一段可以整段粘进任意 AI 对话框的提示词。AI 返回一个代码块，用户再粘回界面。

提示词必须自包含：AI 看不到本项目的任何代码，所以契约、约束、示例都要写全。
"""

from __future__ import annotations

_HEAD = """\
你是一名 Python 脚本作者。请为一个本地文本处理工具写一个「处理器」脚本。

## 输出格式
- 只输出一个 ```python 代码块，代码块前后不要写任何解释、不要写使用说明。
- 代码必须是完整可运行的单文件，不依赖任何第三方库，也不依赖这个工具的任何模块。
- 注释与界面文案一律用中文。

## 文件结构
每个处理器是一个独立的 .py 文件，必须定义两个顶层函数：init() 和 process()。

### init()
无参数，返回一个字典：

```python
{
    "name": "显示给用户的名字",        # 中文，4-10 个字，不要带标点
    "desc": "一句话说明它做什么",      # 中文，30 字以内
    "type": "line",                  # line / file / check 三选一
    "args": {                        # 没有参数就写 {}，不要省略
        "参数ID": {
            "name": "参数名",         # 中文
            "type": "str",           # str / text / int / float / bool / choice
            "default": "默认值",
            "desc": "这个参数的作用",  # 中文，可省略
        },
    },
}
```

参数声明里可用的附加键：
- int / float 可以写 "min" 与 "max" 限定范围。
- choice 必须写 "options": [{"value": "a", "label": "选项 A"}, ...]，且 default 必须是其中一个 value。
- "text" 与 "str" 的区别：text 在界面上是多行输入框，适合放一段较长的文本。

### process()
三种 type 对应三种签名，参数按 args 里的参数 ID 以**关键字参数**传入，
所以 process 的形参名必须与参数 ID 完全一致：

| type | 签名 | 返回值 |
|---|---|---|
| line | process(line, **args) | 这一行处理后的字符串 |
| file | process(text, **args) | 整篇文本处理后的字符串 |
| check | process(line, **args) | 没问题返回 None / False / ""；有问题返回 True，或返回一句中文原因（会被显示给用户） |

## 硬性约束
1. 纯计算：不读写文件、不访问网络、不启动进程、不改全局状态、不打印。
2. 只允许导入这些标准库：re、string、unicodedata、math、json、textwrap、difflib、
   collections、itertools、functools、typing、dataclasses、datetime、hashlib、
   base64、html、statistics、decimal、fractions、operator、copy、random、enum、abc、
   numbers、bisect、heapq、struct、zlib、codecs。禁止导入 os、sys、subprocess、
   socket、shutil、ctypes、pathlib、urllib、requests 等。
3. 文件被加载时只能定义函数和常量，不要有顶层副作用，不要写
   ``if __name__ == "__main__"``。
4. 必须能处理空字符串、只有空白字符的行、超长的行，不能抛异常。
5. 不要反问、不要输出多个方案；需求有歧义时选最合理的一种做法。
6. 性能要求：可能一次处理十万行，process 里不要写嵌套循环扫全表这种重活。

## 示例一：逐行处理

```python
def init():
    return {
        "name": "去除首尾空白",
        "desc": "去掉每行开头和结尾的空白字符",
        "type": "line",
        "args": {
            "chars": {
                "name": "视为空白的字符",
                "type": "str",
                "default": " \\u3000\\t",
                "desc": "这些字符出现在行首或行尾时会被删除",
            }
        },
    }


def process(line, chars):
    return line.strip(chars)
```

## 示例二：检查并给出原因

```python
def init():
    return {
        "name": "检查行末标点",
        "desc": "标出行尾不是句末标点的行",
        "type": "check",
        "args": {
            "chars": {
                "name": "允许的行末字符",
                "type": "str",
                "default": "。？！…”）—：",
            }
        },
    }


def process(line, chars):
    stripped = line.rstrip()
    if not stripped:
        return None
    if stripped[-1] not in chars:
        return "行尾是「" + stripped[-1] + "」，不是句末标点"
    return None
```

## 示例三：整篇处理

```python
def init():
    return {
        "name": "合并断行",
        "desc": "把被硬换行拆开的段落接回一行",
        "type": "file",
        "args": {},
    }


def process(text):
    out = []
    for line in text.splitlines():
        if out and line and out[-1] and not out[-1].endswith(("。", "！", "？")):
            out[-1] += line.strip()
        else:
            out.append(line)
    return "\\n".join(out)
```

## 用户的需求

{request}

现在请只输出一个 ```python 代码块。
"""


def build(request: str) -> str:
    """把用户的一句话需求包成完整提示词。"""
    cleaned = (request or "").strip()
    if not cleaned:
        cleaned = "（用户没有写具体需求，请给一个最通用的文本清理处理器）"
    return _HEAD.replace("{request}", cleaned)
