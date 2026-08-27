# -*- coding: utf-8 -*-
"""往游戏的 ``start.bat`` 里插一行，开游戏时顺带把本程序拉起来并开始监视。

插进去的是 ``start "chunithm-cun-sorter" "<本程序>" --watch``，那个带引号的
窗口标题同时充当**移除标记**。

文件按**字节**处理（以 ``\\n`` 切行）：已有行的内容原样保留，绝不重新编码
别人的 GBK / UTF-8 批处理文本。我们自己那一行（路径里可能有中文）默认按 GBK
写，中文 Windows 下 cmd 的默认代码页就是它；bat 带 UTF-8 BOM 或者出现过
``chcp 65001`` 时改用 UTF-8。

**输出一律用 CRLF 连接**：cmd 的批处理解析器只有在 CRLF 下才可靠——纯 LF 的
bat 里，``@echo off`` 后面那行的第一个字符会被吞掉，我们插的 ``start`` 会变成
``tart``（实机踩过）。原文件留一份 ``*.cun-backup``，只备份一次。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

MARKER = "chunithm-cun-sorter"
BACKUP_SUFFIX = ".cun-backup"

_UTF8_BOM = b"\xef\xbb\xbf"


def launch_command() -> str:
    """拉起本程序并进入监视模式的命令行。

    打包后是 exe 一个参数；跑源码时要走 ``pythonw.exe main.py``，
    免得每次开游戏都弹一个黑框。
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --watch'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    launcher = pythonw if pythonw.is_file() else exe
    entry = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{launcher}" "{entry}" --watch'


def is_hooked(bat_path: str | Path) -> bool:
    p = Path(bat_path)
    try:
        if not p.is_file():
            return False
        return any(MARKER in _ascii_view(line) for line in _split_lines(p.read_bytes()))
    except OSError:
        return False


def hook(bat_path: str | Path) -> None:
    """在开头的 ``@echo off`` 之后插入（或刷新）自启动行。"""
    p = Path(bat_path)
    original = p.read_bytes()

    backup = p.with_name(p.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(p, backup)

    bom, body = _split_bom(original)
    lines = [ln for ln in _split_lines(body) if MARKER not in _ascii_view(ln)]

    utf8 = bool(bom) or any("chcp 65001" in _ascii_view(ln).lower() for ln in lines)
    encoding = "utf-8" if utf8 else "gbk"
    cmd = f'start "{MARKER}" {launch_command()}'.encode(encoding, errors="replace")

    insert_at = 0
    for i, ln in enumerate(lines):
        if _ascii_view(ln).lstrip().lower().startswith("@echo"):
            insert_at = i + 1
            break
    lines.insert(insert_at, cmd)
    p.write_bytes(bom + _join_lines(lines))


def unhook(bat_path: str | Path) -> None:
    """移除自启动行；没有就什么都不做。"""
    p = Path(bat_path)
    if not p.is_file():
        return
    bom, body = _split_bom(p.read_bytes())
    lines = _split_lines(body)
    kept = [ln for ln in lines if MARKER not in _ascii_view(ln)]
    if len(kept) != len(lines):
        p.write_bytes(bom + _join_lines(kept))


# ----------------------------- 字节级行处理 ---------------------------------
def _split_bom(data: bytes) -> tuple[bytes, bytes]:
    """把开头的 UTF-8 BOM 摘出来单独放。

    不摘的话它会粘在第一行内容前面：``@echo off`` 匹配不上，自启动行被插到
    文件最前面——既排在 ``@echo off`` 之前，又把 BOM 挤到了第二行，
    整个文件就废了。（C# 版本也有这个毛病。）
    """
    return (_UTF8_BOM, data[3:]) if data.startswith(_UTF8_BOM) else (b"", data)
def _split_lines(data: bytes) -> list[bytes]:
    lines: list[bytes] = []
    start = 0
    for i, ch in enumerate(data):
        if ch != 0x0A:                              # \n
            continue
        end = i - 1 if i > start and data[i - 1] == 0x0D else i
        lines.append(data[start:end])
        start = i + 1
    if start < len(data):
        lines.append(data[start:])
    return lines


def _join_lines(lines: list[bytes]) -> bytes:
    return b"\r\n".join(lines) + b"\r\n"            # 末尾留一个换行


def _ascii_view(line: bytes) -> str:
    """行的 Latin-1 视图。ASCII 字节在 GBK 和 UTF-8 里都是 1:1，
    所以拿它做标记 / 关键字的子串判断不受编码影响。"""
    return line.decode("latin-1", errors="replace")
