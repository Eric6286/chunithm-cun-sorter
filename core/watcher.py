# -*- coding: utf-8 -*-
"""常驻的、认得出游戏在不在跑的截图监视器。

轮询进程列表判断游戏状态，不需要改 ``start.bat``。只处理**启动之后**才出现的
截图，已有的存量交给全量扫描——不然每次启动都要重跑一遍几千张。
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from . import classifier, winapi
from .models import Category, CunConfig, OcrRecord
from .ocr import OcrEngine

POLL_SEC = 2.0
#: 文件最后写入超过这么久才算「写完了」，躲开截图工具写一半的瞬间
SETTLE_SEC = 1.0

MatchFn = Callable[[str, OcrRecord, list[Category]], None]
StatusFn = Callable[[str], None]
GetConfigFn = Callable[[], CunConfig]


class Watcher:
    """后台线程里的监视循环。"""

    def __init__(self, get_cfg: GetConfigFn, engine: OcrEngine,
                 on_match: MatchFn | None = None, on_status: StatusFn | None = None) -> None:
        self._get_cfg = get_cfg
        self._engine = engine
        self._on_match = on_match
        self._on_status = on_status
        self._cache_lock = threading.Lock()
        self._cache = classifier.load_cache()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cun-watcher", daemon=True)
        self._thread.start()

    def stop(self, join_timeout: float = 3.0) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=join_timeout)
        self._thread = None

    def seed_cache(self, filename: str, rec: OcrRecord) -> None:
        """给一张判定数据已知的截图（自动截图那条路）预置缓存。

        监视器随后分类它时就不会再走 OCR。立即落盘。
        """
        with self._cache_lock:
            self._cache[filename] = rec
            classifier.save_cache(self._cache)

    # ----------------------------- 内部 -------------------------------------
    def _status(self, msg: str) -> None:
        classifier.log(msg)
        if self._on_status is not None:
            try:
                self._on_status(msg)
            except Exception:                       # noqa: BLE001 - 回调是界面的，不能拖垮监视
                pass

    def _handle(self, path: str, cfg: CunConfig) -> bool:
        with self._cache_lock:
            rec, matches = classifier.process_file(
                path, cfg, self._cache, self._engine, classifier.organize_enabled(cfg))
            classifier.save_cache(self._cache)
        if not matches:
            return False
        keys = "+".join(c.key for c in matches)
        classifier.log(
            f"[MATCH] {Path(path).name} score={rec.score} A={rec.attack} M={rec.miss} -> {keys}")
        if self._on_match is not None:
            try:
                self._on_match(Path(path).name, rec, matches)
            except Exception:                       # noqa: BLE001
                pass
        return True

    @staticmethod
    def _settled(shots_dir: str, name: str, now: float) -> bool:
        try:
            return (now - os.path.getmtime(os.path.join(shots_dir, name))) >= SETTLE_SEC
        except OSError:
            return False

    def _run(self) -> None:
        winapi.set_idle_priority()
        cfg = self._get_cfg()
        shots_dir = cfg.screenshots_dir
        baseline = set(classifier.list_pngs(shots_dir))
        self._status(f"watcher started | mode={cfg.process_mode} | "
                     f"watching {shots_dir} ({len(baseline)} existing ignored)")

        seen: set[str] = set()
        queue: list[str] = []
        game_prev = False
        last_game_check = 0.0
        flush_at: float | None = None

        while not self._stop.is_set():
            cfg = self._get_cfg()
            mode = cfg.process_mode
            game = cfg.game_process or "chusanApp.exe"
            now = time.time()

            ready = sorted(f for f in classifier.list_pngs(shots_dir)
                           if f not in baseline and f not in seen
                           and self._settled(shots_dir, f, now))
            for f in ready:
                seen.add(f)
                if mode == "on_close":
                    queue.append(f)
                else:
                    self._handle(os.path.join(shots_dir, f), cfg)

            if now - last_game_check >= cfg.game_poll_sec:
                last_game_check = now
                running = winapi.is_process_running(game)
                if running != game_prev:
                    game_prev = running
                    self._status("game " + ("running" if running else "closed"))
                    if not running and mode == "on_close" and queue:
                        flush_at = now + cfg.game_exit_grace_sec

            if flush_at is not None and now >= flush_at:
                flush_at = None
                # 收尾再扫一次，把这期间新出现的也带上
                extra = [f for f in classifier.list_pngs(shots_dir)
                         if f not in baseline and f not in seen]
                for f in sorted(set(queue) | set(extra)):
                    seen.add(f)
                    self._handle(os.path.join(shots_dir, f), cfg)
                self._status(f"on_close batch processed ({len(queue)})")
                queue.clear()

            self._stop.wait(POLL_SEC)

        self._status("watcher stopped")
