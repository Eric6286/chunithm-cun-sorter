# -*- coding: utf-8 -*-
"""自动找出 CHUNITHM 的游戏根目录。

首次运行向导先用它猜一次，猜中了用户点「就是这个」就完事，猜不中再去浏览。
三条线索，按可靠度排：

1. **游戏正在跑**——直接问进程要 exe 路径，往上走到根目录。最准。
2. **程序装在游戏目录里**——v1.x 的部署方式（``bin\\cun\\``），从自己所在位置往上找。
3. **配置里已经有线索**——填过截图目录或 start.bat 的话反推。

猜不到就返回 ``None``，让用户自己选，别瞎扫盘。
"""

from __future__ import annotations

from pathlib import Path

from . import paths, winapi
from .config import looks_like_game_root, normalize_game_root
from .models import CunConfig

#: 从某个路径往上最多找几层
_MAX_WALK_UP = 8


def _walk_up(start: Path) -> Path | None:
    for candidate in [start, *start.parents][:_MAX_WALK_UP]:
        if looks_like_game_root(candidate):
            return candidate
    return None


def from_running_game(process_name: str = "chusanApp.exe") -> Path | None:
    """游戏正在跑的话，从它的 exe 路径反推根目录。"""
    pid = winapi.pid_of(process_name)
    if pid == 0:
        return None
    image = winapi.process_image_path(pid)
    if not image:
        return None
    return _walk_up(Path(image).parent)


def from_own_location() -> Path | None:
    """本程序自己就装在游戏目录里（v1.x 的部署方式）时能找到。"""
    return _walk_up(paths.exe_dir())


def from_config(cfg: CunConfig) -> Path | None:
    """配置里已经填过的目录反推。"""
    for hint in (cfg.game_root, cfg.screenshots_dir, cfg.start_bat):
        if not hint:
            continue
        p = Path(hint)
        direct = normalize_game_root(p)
        if direct is not None:
            return direct
        found = _walk_up(p.parent if p.suffix else p)
        if found is not None:
            return found
    return None


def autodetect(cfg: CunConfig | None = None) -> Path | None:
    """按可靠度依次试三条线索，第一个命中的就是它。"""
    process_name = (cfg.game_process if cfg else "") or "chusanApp.exe"
    for probe in (lambda: from_running_game(process_name),
                  lambda: from_config(cfg) if cfg else None,
                  from_own_location):
        try:
            found = probe()
        except OSError:
            found = None
        if found is not None:
            return found
    return None
