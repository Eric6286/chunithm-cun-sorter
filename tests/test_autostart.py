# -*- coding: utf-8 -*-
"""开机自启：改名之后，旧名字下的那条要搬过来，不能留在原地。"""

from __future__ import annotations

import pytest

from core import autostart
from core.version import APP_NAME, LEGACY_APP_NAMES

OLD_NAME = LEGACY_APP_NAMES[0]


class _FakeKey:
    def __init__(self, values: dict[str, str]):
        self.values = values

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeWinreg:
    """够 autostart 用的一小块注册表，全在内存里。"""

    HKEY_CURRENT_USER = object()
    REG_SZ = 1

    def __init__(self, values: dict[str, str]):
        self.values = values

    def CreateKey(self, _root, _path):              # noqa: N802
        return _FakeKey(self.values)

    def OpenKey(self, _root, _path):                # noqa: N802
        return _FakeKey(self.values)

    def SetValueEx(self, key, name, _res, _typ, data):   # noqa: N802
        key.values[name] = data

    def QueryValueEx(self, key, name):              # noqa: N802
        if name not in key.values:
            raise OSError(2, "没有这个值")
        return key.values[name], self.REG_SZ

    def DeleteValue(self, key, name):               # noqa: N802
        if name not in key.values:
            raise OSError(2, "没有这个值")
        del key.values[name]


@pytest.fixture
def registry(monkeypatch):
    def _make(values: dict[str, str] | None = None) -> dict[str, str]:
        store = dict(values or {})
        monkeypatch.setattr(autostart, "winreg", _FakeWinreg(store))
        return store
    return _make


def test_the_entry_left_under_the_old_name_gets_moved_over(registry):
    """值名就是应用名。不搬的话开关显示「关」，而登录时还会去跑那条老命令。"""
    values = registry({OLD_NAME: r'"C:\旧\今天你寸了吗.exe"'})
    autostart.migrate_legacy()
    assert OLD_NAME not in values
    assert values[APP_NAME] == autostart._command()


def test_migration_does_not_switch_autostart_on_by_itself(registry):
    """没设过自启的人，升级一次不该被塞一条。"""
    values = registry({})
    autostart.migrate_legacy()
    assert values == {}


def test_migration_leaves_an_already_current_entry_alone(registry):
    values = registry({APP_NAME: "已经是新的了"})
    autostart.migrate_legacy()
    assert values == {APP_NAME: "已经是新的了"}


def test_turning_the_switch_off_also_clears_the_old_name(registry):
    """旧那条不清，关掉开关之后登录还是会被拉起来。"""
    values = registry({OLD_NAME: "老命令", APP_NAME: "新命令"})
    autostart.set_enabled(False)
    assert values == {}


def test_turning_the_switch_on_does_not_leave_two_entries(registry):
    values = registry({OLD_NAME: "老命令"})
    autostart.set_enabled(True)
    assert list(values) == [APP_NAME]
