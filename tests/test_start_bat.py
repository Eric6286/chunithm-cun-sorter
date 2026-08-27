# -*- coding: utf-8 -*-
"""start.bat 注入：字节级编辑、CRLF、备份、精确还原。"""

from __future__ import annotations

from core import start_bat


def _bat(tmp_path, content: bytes):
    p = tmp_path / "start.bat"
    p.write_bytes(content)
    return p


def test_the_line_goes_right_after_echo_off(tmp_path):
    p = _bat(tmp_path, b"@echo off\r\ncd /d %~dp0\r\nchusanApp.exe\r\n")
    start_bat.hook(p)
    lines = p.read_bytes().split(b"\r\n")
    assert lines[0] == b"@echo off"
    assert start_bat.MARKER.encode() in lines[1]
    assert lines[2] == b"cd /d %~dp0"


def test_an_lf_only_bat_is_rewritten_with_crlf(tmp_path):
    """cmd 对纯 LF 的 bat 会吞掉下一行的第一个字符，实机上把 start 变成 tart。"""
    p = _bat(tmp_path, b"@echo off\ncd /d %~dp0\nchusanApp.exe\n")
    start_bat.hook(p)
    data = p.read_bytes()
    assert b"\r\n" in data
    assert data.replace(b"\r\n", b"").find(b"\n") == -1      # 一个裸 LF 都不许剩


def test_existing_lines_keep_their_exact_bytes(tmp_path):
    """别人的 GBK 批处理文本不能被我们重新编码。"""
    gbk_line = "rem 启动游戏".encode("gbk")
    p = _bat(tmp_path, b"@echo off\r\n" + gbk_line + b"\r\nchusanApp.exe\r\n")
    start_bat.hook(p)
    assert gbk_line in p.read_bytes()


def test_a_utf8_bom_bat_gets_a_utf8_line(tmp_path):
    p = _bat(tmp_path, b"\xef\xbb\xbf@echo off\r\nchusanApp.exe\r\n")
    start_bat.hook(p)
    data = p.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8")                              # 整份仍是合法 UTF-8


def test_chcp_65001_also_selects_utf8(tmp_path):
    p = _bat(tmp_path, b"@echo off\r\nchcp 65001\r\nchusanApp.exe\r\n")
    start_bat.hook(p)
    p.read_bytes().decode("utf-8")                           # 不抛异常即通过


def test_hooking_is_idempotent(tmp_path):
    p = _bat(tmp_path, b"@echo off\r\nchusanApp.exe\r\n")
    start_bat.hook(p)
    start_bat.hook(p)
    assert p.read_bytes().count(start_bat.MARKER.encode()) == 1


def test_unhook_restores_the_original_content(tmp_path):
    original = b"@echo off\r\ncd /d %~dp0\r\nchusanApp.exe\r\n"
    p = _bat(tmp_path, original)
    start_bat.hook(p)
    assert start_bat.is_hooked(p)
    start_bat.unhook(p)
    assert not start_bat.is_hooked(p)
    assert p.read_bytes() == original


def test_a_backup_is_made_once_and_never_overwritten(tmp_path):
    original = b"@echo off\r\nchusanApp.exe\r\n"
    p = _bat(tmp_path, original)
    start_bat.hook(p)
    backup = p.with_name(p.name + start_bat.BACKUP_SUFFIX)
    assert backup.read_bytes() == original

    start_bat.unhook(p)
    p.write_bytes(b"@echo off\r\nrem " + "用户后来改的".encode("gbk") + b"\r\n")
    start_bat.hook(p)
    assert backup.read_bytes() == original       # 备份还是最初那份


def test_a_bat_without_echo_off_gets_the_line_first(tmp_path):
    p = _bat(tmp_path, b"chusanApp.exe\r\n")
    start_bat.hook(p)
    assert start_bat.MARKER.encode() in p.read_bytes().split(b"\r\n")[0]


def test_unhook_on_a_missing_file_is_a_noop(tmp_path):
    start_bat.unhook(tmp_path / "根本不存在.bat")     # 不抛异常即通过


def test_is_hooked_is_false_for_an_untouched_bat(tmp_path):
    assert not start_bat.is_hooked(_bat(tmp_path, b"@echo off\r\nchusanApp.exe\r\n"))
