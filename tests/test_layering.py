# -*- coding: utf-8 -*-
"""分层不变量：``core/`` 不许依赖 ``ui/``，也不许依赖 PySide6。

命令行入口和这套测试要能在没装 PySide6 的解释器里跑。这一条只有**从零起一个
新进程**才测得准：当前进程里 PySide6 可能已经被别的测试导入过，
`sys.modules` 一命中就什么都发现不了。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_PROBE = """
import sys
from importlib.abc import MetaPathFinder


class BlockPySide6(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == "PySide6":
            raise ImportError("PySide6 在这次探测里被故意屏蔽")
        return None


sys.meta_path.insert(0, BlockPySide6())
sys.path.insert(0, PROJECT_ROOT)

from core import (autostart, capture, classifier, config, game_locator,      # noqa: F401
                  judge_memory, link_server, models, ocr, paths, start_bat,
                  watcher, winapi)
import cli                                                                    # noqa: F401

assert not any(m.startswith("PySide6") for m in sys.modules), "core 层把 PySide6 拉进来了"
print("OK")
"""


def _run_probe(source: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", f"PROJECT_ROOT = {str(ROOT)!r}\n{source}"],
        capture_output=True, cwd=str(ROOT))


def test_the_core_layer_imports_without_pyside6():
    result = _run_probe(_PROBE)
    stderr = result.stderr.decode("utf-8", "replace")
    assert result.returncode == 0, stderr
    assert b"OK" in result.stdout, stderr


def test_importing_the_ui_package_pulls_in_no_window():
    """``import ui`` 不该顺带把主窗口和整套页面拉起来。

    急切导入会让 ``import ui.theme`` 这种轻量用途也付全套代价，而且一旦某个页面
    有导入期副作用，排查起来完全看不出因果。
    """
    probe = """
import sys
sys.path.insert(0, PROJECT_ROOT)
import ui
assert "ui.main_window" not in sys.modules, "ui/__init__.py 做了急切导入"
assert "ui.page_config" not in sys.modules, "ui/__init__.py 做了急切导入"
print("OK")
"""
    result = _run_probe(probe)
    stderr = result.stderr.decode("utf-8", "replace")
    assert result.returncode == 0, stderr
    assert b"OK" in result.stdout, stderr


def test_no_core_module_imports_the_ui_package():
    """静态检查一遍，方向反了会立刻被发现。"""
    offenders = []
    for path in (ROOT / "core").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ui", "from ui")):
                offenders.append(f"{path.name}: {stripped}")
    assert not offenders, offenders
