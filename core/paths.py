# -*- coding: utf-8 -*-
"""配置、缓存、日志落在哪里。

v2 起程序不再要求装进游戏目录，数据默认落 ``%LOCALAPPDATA%\\ChunithmCunSorter\\``。
两种例外都保留：

* **便携模式**：exe 同级或任一上级目录里有 ``cun_config.json`` 就用那个目录。
  v1.x 是这么部署的（exe 在 ``bin\\cun\\app\\``、配置在 ``bin\\cun\\``），
  老用户原地升级不会丢配置。
* **环境变量**：``CUN_DATA_DIR`` 优先于以上两者，给测试和多开用。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: 数据目录名（ASCII，避免某些工具在带中文的路径上翻车）
DATA_DIR_NAME = "ChunithmCunSorter"

CONFIG_NAME = "cun_config.json"
CACHE_NAME = "cun_ocr_cache.json"
LOG_NAME = "cun.log"

#: 安装器写下的引导文件，第一次运行时读它拿到游戏目录
INSTALL_INI_NAME = "install.ini"


def is_frozen() -> bool:
    """当前是不是 PyInstaller 打出来的 exe。"""
    return bool(getattr(sys, "frozen", False))


def exe_dir() -> Path:
    """程序所在目录：打包后是 exe 的目录，源码运行时是仓库根目录。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """随包分发的只读资源（图标等）的路径。

    PyInstaller 单目录模式把数据文件放进 ``_internal``，``sys._MEIPASS`` 指向那里；
    源码运行时就是仓库根目录。
    """
    base = Path(getattr(sys, "_MEIPASS", exe_dir()))
    return base.joinpath(*parts)


def portable_dir() -> Path | None:
    """便携模式的数据目录：从 exe 目录逐级向上找 ``cun_config.json``。"""
    d = exe_dir()
    for candidate in [d, *d.parents]:
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    return None


def data_dir() -> Path:
    """配置 / 缓存 / 日志 / 诊断截图的落点，必要时创建。"""
    override = os.environ.get("CUN_DATA_DIR", "").strip()
    if override:
        d = Path(override)
    else:
        d = portable_dir() or _default_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _default_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    return Path(local) / DATA_DIR_NAME


def config_path() -> Path:
    return data_dir() / CONFIG_NAME


def cache_path() -> Path:
    return data_dir() / CACHE_NAME


def log_path() -> Path:
    return data_dir() / LOG_NAME


def diag_dir() -> Path:
    return data_dir() / "diag"


def install_ini_path() -> Path:
    """安装器留下的引导文件，和 exe 放一起。"""
    return exe_dir() / INSTALL_INI_NAME
