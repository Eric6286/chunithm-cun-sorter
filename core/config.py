# -*- coding: utf-8 -*-
"""配置的读写、迁移与路径推导。

对外只有几个函数：:func:`load`、:func:`load_cached`、:func:`save`、
:func:`rank_of`、:func:`ranks`，以及给首次运行向导用的 :func:`derive_paths`。
"""

from __future__ import annotations

import configparser
import json
import os
import shutil
import threading
from pathlib import Path

from . import paths
from .models import ORGANIZE_KINDS, Category, CunConfig, DgHubConfig, CaptureConfig, OrganizeStep

#: 内置的「评级判定」得分档位（名称 + 闭区间）。
#: 添加规则对话框和 v1.1→v1.2 的迁移都从这里取，只有这一份。
SCORE_PRESETS: tuple[tuple[str, int, int], ...] = (
    ("SSS+寸", 1008600, 1008999),
    ("SSS寸", 1007000, 1007499),
    ("SS+寸", 1004500, 1004999),
    ("SS寸", 999500, 999999),
)

#: v1.1 内置预设规则的 key。升级时丢掉它们（在添加对话框里能重建），
#: 但**其它规则一律保留**——用户手动加过或改过的规则不能因为文件早于
#: ``custom`` 字段就被静默清掉。
_LEGACY_BUILTIN_KEYS = frozenset({
    "AJ", "FC", "AJ寸", "AM寸", "SSS+寸", "SSS寸", "SS+寸", "SS寸",
})


def load(path: str | os.PathLike[str] | None = None) -> CunConfig:
    """读一份可写的配置快照，缺省项补默认值、路径补全、老格式迁移。"""
    p = Path(path) if path else paths.config_path()
    cfg = CunConfig()
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            cfg = CunConfig.from_dict(raw)
        except (OSError, ValueError) as e:
            print(f"配置读取失败（{e}），改用默认值")

    _migrate_categories(cfg)
    _ensure_organize_steps(cfg)
    _apply_install_hint(cfg, p)
    _fill_paths(cfg)
    _resolve_tesseract(cfg)
    return cfg


_cache_lock = threading.Lock()
_cached: CunConfig | None = None
_cached_stamp: float = -1.0


def load_cached() -> CunConfig:
    """给热路径（监视线程 2 秒一轮、内存读取 20Hz）用的带缓存版本。

    只有 ``cun_config.json`` 的修改时间变了才重新解析，否则复用上一份。
    **调用方要当只读用**（这是共享实例）；需要一份能改的就调 :func:`load`。
    """
    global _cached, _cached_stamp
    with _cache_lock:
        try:
            p = paths.config_path()
            stamp = p.stat().st_mtime if p.is_file() else -1.0
            if _cached is not None and stamp == _cached_stamp:
                return _cached
            _cached = load()
            _cached_stamp = stamp
            return _cached
        except OSError:
            if _cached is not None:
                return _cached
            return load()


def invalidate_cache() -> None:
    """强制下一次 :func:`load_cached` 重新读盘（保存之后调）。"""
    global _cached_stamp
    with _cache_lock:
        _cached_stamp = -1.0


def save(cfg: CunConfig, path: str | os.PathLike[str] | None = None) -> None:
    """原子写回配置：先写 ``.tmp`` 再替换，中途断电不会留下半个文件。"""
    p = Path(path) if path else paths.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(
        json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, p)
    invalidate_cache()


def rank_of(score: int | None, cfg: CunConfig) -> str | None:
    """得分对应的评级；``None`` 进 ``None`` 出。"""
    if score is None:
        return None
    for name, thr in sorted(cfg.rank_thresholds.items(), key=lambda kv: kv[1], reverse=True):
        if score >= thr:
            return name
    return "D"


def ranks(cfg: CunConfig) -> list[str]:
    """评级由高到低，配置页下拉框用。"""
    return [k for k, _ in sorted(cfg.rank_thresholds.items(), key=lambda kv: kv[1], reverse=True)]


# ----------------------------- 游戏目录 -------------------------------------
def looks_like_game_root(d: str | os.PathLike[str]) -> bool:
    """这个目录像不像 CHUNITHM 的游戏根目录。

    判据是根目录下有 ``bin\\``，且 ``bin\\`` 里能找到 ``screenshots``、
    ``chusanApp.exe`` 或 ``option`` 之一；根目录有 ``start.bat`` 也算。
    """
    root = Path(d)
    if not root.is_dir():
        return False
    bin_dir = root / "bin"
    if not bin_dir.is_dir():
        return False
    if (root / "start.bat").is_file():
        return True
    return any((bin_dir / n).exists() for n in ("screenshots", "chusanApp.exe", "option"))


def normalize_game_root(d: str | os.PathLike[str]) -> Path | None:
    """把用户选的目录归一成游戏根目录。

    直接选中根目录、或者选中了根目录下的 ``bin\\`` 都接受；都不像就返回 ``None``。
    """
    p = Path(d)
    if looks_like_game_root(p):
        return p
    if p.name.lower() == "bin" and looks_like_game_root(p.parent):
        return p.parent
    return None


def derive_paths(game_root: str | os.PathLike[str]) -> tuple[str, str]:
    """由游戏根目录推出 ``(截图目录, start.bat 路径)``，推不出的给空串。"""
    root = Path(game_root)
    shots = root / "bin" / "screenshots"
    bat = ""
    for cand in (root / "start.bat", root / "bin" / "start.bat"):
        if cand.is_file():
            bat = str(cand)
            break
    return str(shots), bat


def apply_game_root(cfg: CunConfig, game_root: str | os.PathLike[str]) -> None:
    """把游戏目录写进配置，并顺带补上截图 / 输出 / start.bat。

    空着的项直接填。已经有值的项**只在它就是上一个游戏目录推出来的那个值时**才替换——
    换游戏安装位置时这几个路径要跟着走，但用户手动指定过的目录不能被顶掉。
    """
    root = Path(game_root)
    old_shots, old_bat = derive_paths(cfg.game_root) if cfg.game_root else ("", "")
    new_shots, new_bat = derive_paths(root)

    if not cfg.screenshots_dir or _same_path(cfg.screenshots_dir, old_shots):
        follows_shots = not cfg.output_root or _same_path(cfg.output_root, cfg.screenshots_dir)
        cfg.screenshots_dir = new_shots
        if follows_shots:
            cfg.output_root = new_shots
    if not cfg.output_root:
        cfg.output_root = cfg.screenshots_dir
    if not cfg.start_bat or _same_path(cfg.start_bat, old_bat):
        if new_bat:
            cfg.start_bat = new_bat

    cfg.game_root = str(root)


def _same_path(a: str, b: str) -> bool:
    if not a or not b:
        return False
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except (OSError, ValueError):
        return a == b


# ----------------------------- 内部 -----------------------------------------
def _migrate_categories(cfg: CunConfig) -> None:
    """v1.1→v1.2 迁移：丢掉旧内置预设，其余一律保留并标成自定义。"""
    kept = [c for c in cfg.categories if c.custom or c.key not in _LEGACY_BUILTIN_KEYS]
    for c in kept:
        c.custom = True
    cfg.categories = kept


def _ensure_organize_steps(cfg: CunConfig) -> None:
    """保住用户的排序，但三个整理维度必须各出现一次，未知的 kind 丢掉。"""
    seen: dict[str, OrganizeStep] = {}
    ordered: list[OrganizeStep] = []
    for s in cfg.organize.steps:
        if s.kind in ORGANIZE_KINDS and s.kind not in seen:
            seen[s.kind] = s
            ordered.append(s)
    for kind in ORGANIZE_KINDS:
        if kind not in seen:
            ordered.append(OrganizeStep(kind=kind))
    cfg.organize.steps = ordered


def _apply_install_hint(cfg: CunConfig, config_file: Path) -> None:
    """吃掉安装器留下的 ``install.ini``。

    安装向导里选的游戏目录写在那儿，第一次运行时搬进配置。只在配置还没有
    截图目录时生效——升级重装不会把用户后来改过的目录顶回去。
    """
    if cfg.screenshots_dir:
        return
    ini = paths.install_ini_path()
    if not ini.is_file():
        return
    try:
        parser = configparser.ConfigParser()
        parser.read(ini, encoding="utf-8-sig")
        root = parser.get("cun", "game_root", fallback="").strip()
    except (OSError, configparser.Error):
        return
    if not root or not Path(root).is_dir():
        return
    apply_game_root(cfg, root)
    try:
        save(cfg, config_file)
    except OSError:
        pass    # 写不进去也不影响本次运行，下次再试


def _fill_paths(cfg: CunConfig) -> None:
    """补全截图 / 输出目录。

    优先用配置里的游戏根目录；没有的话退回 v1.x 的便携规则
    （数据目录的上一级里的 ``screenshots``），这样老的「装在 bin\\cun\\」
    部署原地升级仍然指得对。

    ⚠️ 便携那条只在**真的处于便携模式**时才走。光看「往上找得到
    cun_config.json」是不够的：源码仓库里放一份种子配置就会让开发时的运行
    误判成便携部署，把截图目录推到仓库旁边去（踩过）。
    """
    if not cfg.screenshots_dir and cfg.game_root:
        cfg.screenshots_dir = derive_paths(cfg.game_root)[0]
    if not cfg.screenshots_dir:
        portable = paths.portable_dir()
        if portable is not None and _same_path(str(portable), str(paths.data_dir())):
            cfg.screenshots_dir = str((portable.parent / "screenshots").resolve())
    if not cfg.output_root:
        cfg.output_root = cfg.screenshots_dir


def _resolve_tesseract(cfg: CunConfig) -> None:
    """配置里那个 tesseract.exe 不存在就去 PATH 上找一个。"""
    if cfg.tesseract_cmd and Path(cfg.tesseract_cmd).is_file():
        return
    found = shutil.which("tesseract")
    if found:
        cfg.tesseract_cmd = found
