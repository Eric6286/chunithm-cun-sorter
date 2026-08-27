# -*- coding: utf-8 -*-
"""命令行入口，不依赖 PySide6。

    python cli.py scan                 # 全量扫描（沿用缓存）
    python cli.py scan --rebuild       # 先清掉旧副本再扫
    python cli.py scan --reocr         # 丢掉缓存重新识别
    python cli.py watch                # 无界面常驻监视，Ctrl-C 停
    python cli.py stats                # 打印每日统计
    python cli.py config               # 打印当前配置的关键项
    python cli.py game-root <目录>      # 设置 CHUNITHM 游戏目录（安装器也走这条）
"""

from __future__ import annotations

import argparse
import sys
import time

from core import classifier, game_locator, paths
from core import config as config_mod
from core.ocr import OcrEngine
from core.version import APP_NAME, __version__


def _cmd_scan(args: argparse.Namespace) -> int:
    cfg = config_mod.load()
    if not cfg.screenshots_dir:
        print("截图目录还没设置。先跑：python cli.py game-root <CHUNITHM 目录>")
        return 2
    if not OcrEngine.available(cfg) and not args.reocr:
        print("警告：找不到 tesseract.exe，只有缓存里已有的图能算数。")

    last = [0.0]

    def progress(done: int, total: int, cun: int, aj: int) -> None:
        now = time.monotonic()
        if now - last[0] < 0.5 and done != total:
            return
        last[0] = now
        print(f"\r  {done}/{total}    寸 {cun}    AJ {aj}", end="", flush=True)

    with OcrEngine() as engine:
        result = classifier.scan_all(cfg, engine, progress=progress,
                                     rebuild=args.rebuild, reocr=args.reocr)
    print()
    print(f"扫描完成：共 {result.total} 张，寸 {result.cun}，AJ {result.aj}")
    return 0


def _cmd_watch(_args: argparse.Namespace) -> int:
    from core.watcher import Watcher

    cfg = config_mod.load()
    if not cfg.screenshots_dir:
        print("截图目录还没设置。先跑：python cli.py game-root <CHUNITHM 目录>")
        return 2

    with OcrEngine() as engine:
        watcher = Watcher(
            get_cfg=config_mod.load_cached,
            engine=engine,
            on_match=lambda f, rec, m: print(
                f"✓ {f}  得分={rec.score} A={rec.attack} M={rec.miss}  "
                f"[{'+'.join(c.key for c in m)}]"),
            on_status=print,
        )
        watcher.start()
        print("监视中，Ctrl-C 停止。")
        try:
            while watcher.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n停止中…")
        finally:
            watcher.stop()
    return 0


def _cmd_stats(_args: argparse.Namespace) -> int:
    cfg = config_mod.load()
    rows = classifier.daily_counts(cfg)
    if not rows:
        print("还没有数据。先跑一次 scan。")
        return 0
    print(f"{'日期':<12}{'寸':>6}{'AJ':>6}{'FC':>6}")
    for date, cun, aj, fc in rows:
        print(f"{date:<12}{cun:>6}{aj:>6}{fc:>6}")
    total = sum(r[1] for r in rows)
    print(f"{'累计':<12}{total:>6}")
    return 0


def _cmd_config(_args: argparse.Namespace) -> int:
    cfg = config_mod.load()
    print(f"配置文件      {paths.config_path()}")
    print(f"游戏目录      {cfg.game_root or '（未设置）'}")
    print(f"截图目录      {cfg.screenshots_dir or '（未设置）'}")
    print(f"输出目录      {cfg.output_root or '（未设置）'}")
    print(f"start.bat     {cfg.start_bat or '（未接入）'}")
    print(f"Tesseract     {OcrEngine.tesseract_exe(cfg) or '（找不到）'}")
    print(f"处理模式      {cfg.process_mode}")
    print(f"DGHub 联动    {'开' if cfg.dghub.enabled else '关'}（端口 {cfg.dghub.port}）")
    print(f"自动截图      {'开' if cfg.capture.enabled else '关'}"
          f"（等待 {cfg.capture.delay_s} 秒）")
    print(f"判定规则      {len(cfg.categories)} 条，"
          f"启用 {sum(1 for c in cfg.categories if c.enabled)} 条")
    enabled_steps = [s.kind for s in cfg.organize.steps if s.enabled]
    print(f"整理维度      {' / '.join(enabled_steps) if enabled_steps else '（未启用）'}")
    return 0


def _cmd_game_root(args: argparse.Namespace) -> int:
    cfg = config_mod.load()
    if args.path:
        root = config_mod.normalize_game_root(args.path)
        if root is None:
            print(f"「{args.path}」不像 CHUNITHM 的安装位置：里面应该有一个 bin 文件夹。")
            return 2
    else:
        root = game_locator.autodetect(cfg)
        if root is None:
            print("没能自动找到游戏目录，手动给一个：python cli.py game-root <目录>")
            return 2
        print(f"自动找到：{root}")

    config_mod.apply_game_root(cfg, root)
    config_mod.save(cfg)
    print(f"游戏目录      {cfg.game_root}")
    print(f"截图目录      {cfg.screenshots_dir}")
    print(f"输出目录      {cfg.output_root}")
    if cfg.start_bat:
        print(f"start.bat     {cfg.start_bat}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cun", description=f"{APP_NAME} · 命令行")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="全量扫描截图目录")
    scan.add_argument("--rebuild", action="store_true", help="先清掉本工具生成的副本")
    scan.add_argument("--reocr", action="store_true", help="丢掉缓存重新识别")
    scan.set_defaults(func=_cmd_scan)

    watch = sub.add_parser("watch", help="常驻监视新截图")
    watch.set_defaults(func=_cmd_watch)

    stats = sub.add_parser("stats", help="打印每日统计")
    stats.set_defaults(func=_cmd_stats)

    config = sub.add_parser("config", help="打印当前配置")
    config.set_defaults(func=_cmd_config)

    root = sub.add_parser("game-root", help="设置 CHUNITHM 游戏目录")
    root.add_argument("path", nargs="?", help="游戏根目录；不给就自动探测")
    root.set_defaults(func=_cmd_game_root)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
