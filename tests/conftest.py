# -*- coding: utf-8 -*-
"""测试共用的夹具。

**每个测试都跑在自己的数据目录里**（``CUN_DATA_DIR`` 指向 tmp_path），
绝不碰真实的 ``%LOCALAPPDATA%\\ChunithmCunSorter``。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config as config_mod          # noqa: E402
from core.models import Category, CunConfig    # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """把数据目录钉在 tmp_path 上，并清掉配置缓存。"""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("CUN_DATA_DIR", str(data))
    config_mod.invalidate_cache()
    yield data
    config_mod.invalidate_cache()


@pytest.fixture
def game_tree(tmp_path):
    """一棵长得像 CHUNITHM 安装目录的假目录树。"""
    root = tmp_path / "CHUNITHM"
    (root / "bin" / "screenshots").mkdir(parents=True)
    (root / "bin" / "option").mkdir()
    (root / "start.bat").write_bytes(b"@echo off\r\nchusanApp.exe\r\n")
    return root


@pytest.fixture
def cfg(tmp_path) -> CunConfig:
    """一份指向 tmp_path 的最小可用配置。"""
    shots = tmp_path / "shots"
    shots.mkdir()
    c = CunConfig()
    c.screenshots_dir = str(shots)
    c.output_root = str(shots)
    return c


@pytest.fixture
def sss_rule() -> Category:
    return Category(key="SSS寸", label="SSS寸", kind="score", enabled=True,
                    folder="寸/SSS寸", custom=True, lo=1007000, hi=1007499)
