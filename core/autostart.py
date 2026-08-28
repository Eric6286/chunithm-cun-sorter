# -*- coding: utf-8 -*-
"""开机自启开关，写 ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``。"""

from __future__ import annotations

import sys

from .start_bat import launch_command
from .version import APP_NAME, LEGACY_APP_NAMES

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

if sys.platform == "win32":
    import winreg
else:                                               # 非 Windows 上留个空壳，方便导入做测试
    winreg = None                                   # type: ignore[assignment]


def _command() -> str:
    """开机要跑的命令。不带 ``--watch``，登录时只把界面拉起来，别自己开始监视。"""
    return launch_command().replace(" --watch", "")


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if winreg is None:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            _drop_legacy(key)
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except OSError:
                    pass                            # 本来就没有
    except OSError:
        pass                                        # 尽力而为，写不进注册表不该崩


def migrate_legacy() -> None:
    """把旧名字下的自启项搬到现在的名字上，启动时调一次。

    注册表值名就是应用名，改名之后旧那条既不会被 :func:`is_enabled` 看见，
    命令里指的又是改名前的 exe 文件名——不搬的话，开机自启会在用户不知情的
    情况下静默失效，界面上的开关还显示着「关」。
    """
    if winreg is None:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            if not _drop_legacy(key):
                return
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
    except OSError:
        pass


def _drop_legacy(key) -> bool:
    """删掉旧名字下的自启项，返回本来有没有。"""
    found = False
    for name in LEGACY_APP_NAMES:
        try:
            winreg.DeleteValue(key, name)
            found = True
        except OSError:
            pass
    return found
