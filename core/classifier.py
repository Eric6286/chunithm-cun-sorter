# -*- coding: utf-8 -*-
"""判定、复制、整理、扫描、缓存和每日统计。

两件事分得很清楚：

* **判定命中**只**复制**原图到 ``寸/`` 下的规则文件夹，原图一动不动；
* **整理**才会**移动**原图，而且只移动识别出成绩的结算截图——壁纸和识别失败的
  图片永远留在原地。

OCR 结果缓存在 ``cun_ocr_cache.json``，改完规则重判是瞬间的事，不用重新识别。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Callable, Iterable, MutableSet
from datetime import datetime
from pathlib import Path

from . import config as config_mod
from . import paths
from .models import Category, CunConfig, OcrRecord, ScanResult
from .ocr import OcrEngine

#: 算「寸」的规则类型（结算联动判定也用这一份）
CUN_KINDS = frozenset({"score", "am", "ajcun"})

#: 工具自己复制出来的副本，文件名里一定有这个标记
COPY_MARKER = "__"

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

ProgressFn = Callable[[int, int, int, int], None]


# ----------------------------- 日志 -----------------------------------------
def log(msg: str) -> str:
    """往 ``cun.log`` 追加一行，同时把这行返回给调用方显示。"""
    line = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    try:
        with paths.log_path().open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    return line


# ----------------------------- 缓存 -----------------------------------------
def list_pngs(directory: str | os.PathLike[str]) -> list[str]:
    """目录下的 PNG 文件名（不递归）。目录不存在就返回空列表。"""
    try:
        return [e.name for e in os.scandir(directory)
                if e.is_file() and e.name.lower().endswith(".png")]
    except OSError:
        return []


def load_cache() -> dict[str, OcrRecord]:
    p = paths.cache_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): OcrRecord.from_dict(v) for k, v in raw.items()}


def save_cache(cache: dict[str, OcrRecord]) -> None:
    p = paths.cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(
        json.dumps({k: v.to_dict() for k, v in cache.items()}, ensure_ascii=False),
        encoding="utf-8")
    os.replace(tmp, p)


def get_ocr(path: str | Path, cfg: CunConfig, cache: dict[str, OcrRecord],
            engine: OcrEngine) -> OcrRecord:
    """取一张图的判定数据，第一次见到才真去识别。

    缓存按**裸文件名**索引，所以还要比对文件大小：扫描是递归的，
    不同子目录下重名的两张图否则会串到一起。老记录没存大小（``None``），
    按匹配处理，保持向后兼容。
    """
    p = Path(path)
    name = p.name
    try:
        size: int | None = p.stat().st_size
    except OSError:
        size = None

    rec = cache.get(name)
    if rec is not None and (rec.size is None or rec.size == size):
        return rec

    result = engine.detect(p, cfg)
    rec = result.to_record(size)
    cache[name] = rec
    return rec


# ----------------------------- 判定 -----------------------------------------
def classify(score: int | None, attack: int | None, miss: int | None,
             cfg: CunConfig) -> list[Category]:
    """跑一遍所有启用的规则，返回命中的那些。"""
    hits: list[Category] = []
    for cat in cfg.categories:
        if not cat.enabled:
            continue
        kind = cat.kind
        if kind == "aj":
            # aj / fc 是早期的规则类型，界面上已经建不出来了（AJ/FC 现在是内建属性）。
            # 手写配置里可能还有，条件跟 is_aj / is_fc 保持一致。
            if attack == 0 and miss == 0:
                hits.append(cat)
        elif kind == "fc":
            if attack is not None and miss is not None and attack != 0 and miss == 0:
                hits.append(cat)
        elif kind == "ajcun":                       # 差一点 AJ：A=0，0<M≤x
            if attack == 0 and miss is not None and 0 < miss <= (cat.m_hi if cat.m_hi is not None else 4):
                hits.append(cat)
        elif kind == "score":
            lo = cat.lo if cat.lo is not None else 0
            hi = cat.hi if cat.hi is not None else 0
            if score is not None and lo <= score <= hi:
                hits.append(cat)
        elif kind == "am":                          # A≤a_hi、M≤m_hi、A+M>0、评级≥门槛
            if score is None or attack is None or miss is None:
                continue
            if cat.min_rank is not None:
                floor = cfg.rank_thresholds.get(cat.min_rank, 1007500)
            else:
                floor = cat.score_min if cat.score_min is not None else 1007500
            a_hi = cat.a_hi if cat.a_hi is not None else 4
            m_hi = cat.m_hi if cat.m_hi is not None else 4
            if score >= floor and attack <= a_hi and miss <= m_hi and (attack + miss) > 0:
                hits.append(cat)
    return hits


def is_aj(rec: OcrRecord) -> bool:
    """AJ（All Justice）：ATTACK=0 且 MISS=0。整理文件夹、扫描计数、每日统计共用这一个定义。"""
    return rec.attack == 0 and rec.miss == 0


def is_fc(rec: OcrRecord) -> bool:
    """FC（Full Combo）：没有 MISS，但至少吃了一个 ATTACK。"""
    return rec.miss == 0 and rec.attack is not None and rec.attack > 0


# ----------------------------- 复制 -----------------------------------------
def _sanitize(s: str) -> str:
    return s.replace("+", "p").replace("/", "_").replace("\\", "_")


def _none_str(x: int | None) -> str:
    return "None" if x is None else str(x)


def _out_name(stem: str, ext: str, rank: str | None, rec: OcrRecord,
              cats: list[Category], rename: bool) -> str:
    tag = "+".join(_sanitize(c.key) for c in cats)
    if rename:
        return (f"{stem}{COPY_MARKER}{tag}_{_sanitize(rank or 'NA')}"
                f"_A{_none_str(rec.attack)}M{_none_str(rec.miss)}_{_none_str(rec.score)}{ext}")
    return f"{stem}{COPY_MARKER}{tag}{ext}"


def copy_matches(path: str | Path, rec: OcrRecord, matches: list[Category],
                 cfg: CunConfig) -> list[str]:
    """把截图复制进每条命中规则的目标文件夹。"""
    by_folder: dict[str, list[Category]] = {}
    for c in matches:
        folder = c.folder or cfg.cun_folder
        by_folder.setdefault(folder, []).append(c)

    p = Path(path)
    rank = config_mod.rank_of(rec.score, cfg)
    copied: list[str] = []
    for folder, cats in by_folder.items():
        parts = [x for x in folder.replace("\\", "/").split("/") if x]   # 支持 寸/AJ寸 这种嵌套
        dest_dir = Path(cfg.output_root).joinpath(*parts)
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / _out_name(p.stem, p.suffix, rank, rec, cats, cfg.rename_with_stats)
            if not dest.exists():
                shutil.copy2(p, dest)
            copied.append(str(dest))
        except OSError as e:
            log(f"ERROR copying {p.name} -> {folder}: {e}")
    return copied


def clear_tool_files(cfg: CunConfig) -> int:
    """清掉输出目录里**本工具生成的**副本（文件名带 ``__`` 的），递归。

    只在「应用并重新扫描」时调，让规则改动能重建一份干净的结果。
    """
    folders: set[str] = {cfg.cun_folder, cfg.aj_folder, "FC"}
    for c in cfg.categories:
        if c.folder:
            top = c.folder.replace("\\", "/").split("/")[0]
            if top:
                folders.add(top)

    removed = 0
    for folder in folders:
        if not folder:
            continue
        root = Path(cfg.output_root) / folder
        if not root.is_dir():
            continue
        for f in root.rglob("*.png"):
            if COPY_MARKER not in f.name:
                continue
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
    return removed


# ----------------------------- 整理 -----------------------------------------
def organize_enabled(cfg: CunConfig) -> bool:
    return any(s.enabled for s in cfg.organize.steps)


def _date_segment(filename: str, span: str) -> str | None:
    m = _DATE_RE.match(filename)
    if not m:
        return None                     # 文件名里没有日期，这一层跳过
    d = m.group(1)                      # yyyy-MM-dd
    if span == "year":
        return d[:4]
    if span == "day":
        return d
    return d[:7]


def _achievement_segment(rec: OcrRecord) -> str:
    return "AJ" if is_aj(rec) else "FC" if is_fc(rec) else "普通"


def organize_rel_path(filename: str, rec: OcrRecord, cfg: CunConfig) -> str:
    """按启用的整理维度拼出相对路径，如 ``2026-05/SSS+/AJ``。

    取不到值的维度直接跳过，不建「未知」文件夹；全跳过（空串）就意味着
    这张图留在原地不动。
    """
    parts: list[str] = []
    for step in cfg.organize.steps:
        if not step.enabled:
            continue
        if step.kind == "date":
            seg = _date_segment(filename, step.date_span)
        elif step.kind == "rank":
            seg = config_mod.rank_of(rec.score, cfg)
        elif step.kind == "achievement":
            seg = _achievement_segment(rec)
        else:
            seg = None
        if seg:
            parts.append(seg)
    return "/".join(parts)


def _norm(path: str | Path) -> str:
    """比较用的规范路径（Windows 上大小写不敏感）。"""
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except (OSError, ValueError):
        return os.path.normcase(str(path))


def _tool_roots(cfg: CunConfig) -> tuple[list[str], list[str]]:
    """工具自己的输出目录，分两组。

    **规则目录**（``寸`` 加每条规则文件夹的第一段）里只会有我们的副本，
    扫描按**位置**整个跳过——比按文件名判断稳，用户截图里碰巧带 ``__`` 也不会误伤。

    **达成目录**（``AJ`` / ``FC``）身兼两职：既是「按达成整理」的目的地
    （里面是要继续参与扫描的原图），也可能有早期 AJ/FC 规则留下的副本。
    所以那两个目录下只跳过带 ``__`` 标记的文件。
    """
    rule_names = {cfg.cun_folder}
    for c in cfg.categories:
        if c.folder:
            top = c.folder.replace("\\", "/").split("/")[0]
            if top:
                rule_names.add(top)
    achievement_names = [n for n in (cfg.aj_folder, "FC") if n and n not in rule_names]

    def resolve(names: Iterable[str]) -> list[str]:
        out = []
        for n in names:
            if n:
                out.append(_norm(Path(cfg.output_root) / n))
        return out

    return resolve(rule_names), resolve(achievement_names)


def _is_under(full: str, roots: Iterable[str]) -> bool:
    for r in roots:
        if full == r or full.startswith(r + os.sep):
            return True
    return False


def _unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    i = 1
    while True:
        cand = dest.with_name(f"{dest.stem} ({i}){dest.suffix}")
        if not cand.exists():
            return cand
        i += 1


def _same_size(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size
    except OSError:
        return False


def move_to_organized(path: str | Path, rec: OcrRecord, cfg: CunConfig,
                      emptied: MutableSet[str] | None = None) -> None:
    """把认出成绩的结算截图移进它的归档文件夹。

    不是结算画面（读不到得分）的图一律不动，所以目录里的壁纸不会被搬走。
    已经在位就什么都不做；目的地已经有个一模一样的文件时保留原图不动，
    不生成 ``(1)`` 副本。**只移动，不删除。**
    """
    if rec.score is None:
        return                                      # 不是结算截图，别碰
    p = Path(path)
    rel = organize_rel_path(p.name, rec, cfg)
    if not rel:
        return
    dest_dir = Path(cfg.output_root).joinpath(*rel.split("/"))
    dest = dest_dir / p.name
    if _norm(dest) == _norm(p):
        return

    src_dir = str(Path(_norm(p)).parent)
    try:
        if dest.exists() and _same_size(dest, p):
            if emptied is not None:
                emptied.add(src_dir)
            return
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(_unique_dest(dest)))
        if emptied is not None:
            emptied.add(src_dir)
    except OSError as e:
        log(f"ERROR organize {p.name} -> {rel}: {e}")


def _list_originals(cfg: CunConfig) -> list[str]:
    """所有要处理的原图，在截图目录和输出目录下递归找，排除工具自己的输出目录。

    每次扫描都递归，所以关掉整理之后，之前已经归档进子目录的图仍然会被扫到、
    统计得上——整理开关只决定「要不要接着搬」。
    """
    rule_roots, achievement_roots = _tool_roots(cfg)
    roots = [cfg.screenshots_dir]
    if _norm(cfg.output_root) != _norm(cfg.screenshots_dir):
        roots.append(cfg.output_root)

    seen: set[str] = set()
    result: list[str] = []
    for root in roots:
        rp = Path(root)
        if not rp.is_dir():
            continue
        try:
            candidates = sorted(rp.rglob("*.png"))
        except OSError:
            continue
        for f in candidates:
            full = _norm(f)
            if _is_under(full, rule_roots):
                continue                            # 我们自己的副本，不是原图
            if _is_under(full, achievement_roots) and COPY_MARKER in f.name:
                continue                            # 早期 AJ/FC 规则的副本
            if full in seen:
                continue
            seen.add(full)
            result.append(str(f))
    return result


def _prune_empty_dirs_scoped(dirs: Iterable[str], cfg: CunConfig) -> None:
    """只清理这次整理**搬空的**目录，以及因此连带空掉的父目录。

    往上走到截图 / 输出根目录为止，根目录本身永远不删。不做全盘扫荡，
    用户自己在输出树下留的空文件夹不会被顺手删掉。
    """
    stop = {_norm(cfg.screenshots_dir), _norm(cfg.output_root)}
    for d in dirs:
        cur = d
        while cur and cur not in stop:
            try:
                p = Path(cur)
                if p.is_dir() and not any(p.iterdir()):
                    parent = str(p.parent)
                    p.rmdir()
                    cur = parent
                else:
                    break
            except OSError:
                break


# ----------------------------- 扫描与统计 -----------------------------------
def process_file(path: str | Path, cfg: CunConfig, cache: dict[str, OcrRecord],
                 engine: OcrEngine, organize: bool,
                 emptied: MutableSet[str] | None = None) -> tuple[OcrRecord, list[Category]]:
    """识别 + 判定一张截图：先复制寸命中，再（开了整理的话）搬原图。"""
    rec = get_ocr(path, cfg, cache, engine)
    matches = classify(rec.score, rec.attack, rec.miss, cfg)
    if matches:
        copy_matches(path, rec, matches, cfg)       # 寸副本先出
    if organize:
        move_to_organized(path, rec, cfg, emptied)  # 再搬原图
    return rec, matches


def scan_all(cfg: CunConfig, engine: OcrEngine, progress: ProgressFn | None = None,
             rebuild: bool = False, reocr: bool = False,
             should_stop: Callable[[], bool] | None = None) -> ScanResult:
    """全量扫描。``rebuild`` 先清掉旧副本，``reocr`` 连缓存一起丢掉重认。"""
    cache: dict[str, OcrRecord] = {} if reocr else load_cache()
    organize = organize_enabled(cfg)
    if rebuild:
        clear_tool_files(cfg)

    files = _list_originals(cfg)
    files.sort()

    emptied: set[str] | None = set() if organize else None
    n_cun = n_aj = 0
    done = 0
    for i, f in enumerate(files):
        if should_stop is not None and should_stop():
            break
        rec, matches = process_file(f, cfg, cache, engine, organize, emptied)
        if any(c.kind in CUN_KINDS for c in matches):
            n_cun += 1
        if is_aj(rec):
            n_aj += 1                               # AJ 是内建属性，不再靠规则
        done = i + 1
        if progress is not None and done % 5 == 0:
            progress(done, len(files), n_cun, n_aj)
        if done % 25 == 0:
            save_cache(cache)

    save_cache(cache)
    if emptied:
        _prune_empty_dirs_scoped(emptied, cfg)
    if progress is not None:
        progress(done, len(files), n_cun, n_aj)
    return ScanResult(total=len(files), cun=n_cun, aj=n_aj)


def daily_counts(cfg: CunConfig, cache: dict[str, OcrRecord] | None = None
                 ) -> list[tuple[str, int, int, int]]:
    """按日期排序的 ``(日期, 寸, AJ, FC)``，全部由缓存 + 当前规则算出来。"""
    if cache is None:
        cache = load_cache()
    days: dict[str, list[int]] = {}
    for filename, rec in cache.items():
        m = _DATE_RE.match(filename)
        if not m:
            continue
        date = m.group(1)
        kinds = {c.kind for c in classify(rec.score, rec.attack, rec.miss, cfg)}
        slot = days.setdefault(date, [0, 0, 0])
        if kinds & CUN_KINDS:
            slot[0] += 1
        if is_aj(rec):
            slot[1] += 1
        elif is_fc(rec):
            slot[2] += 1
    return [(d, v[0], v[1], v[2]) for d, v in sorted(days.items())]
