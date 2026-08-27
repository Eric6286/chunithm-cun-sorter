# -*- coding: utf-8 -*-
"""结算画面自动截图，取代外部截图工具。

内存读取那边发现判定数冻结（＝结算画面已经出来了）之后，这里开始每 0.5 秒
抓一帧游戏画面，确认是成绩画面就等分数滚完再存进截图目录。判定数据直接来自
内存，所以这样存下来的新截图**完全不需要 OCR**。

「是不是成绩画面」靠两道叠加的检查：

1. **17 点 UI 骨架像素指纹**——这些点在全部存量成绩图上恒定不变
   （由 ``tools/gen_result_signature.py`` 从归档统计生成）。打歌画面只命中
   9/17、地图画面 11/17，阈值定在 16/17。
2. **判定明细面板区域均色**——曲终先出现的 CLEAR 过场和成绩画面共享**全部**
   顶部 chrome，单靠指纹分不开（生产环境就是这么截错的）。但成绩画面中部
   有一块深紫色的判定明细面板，CLEAR 那个位置是近白背景，两者差 ≥90。

坐标按 1920×1080 标定，其它分辨率按比例缩放。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import paths, winapi
from .models import CaptureConfig, CunConfig, JudgeCounts

#: (x, y, r, g, b)：在所有成绩截图上都稳定的 UI 骨架采样点
SIGNATURE: tuple[tuple[int, int, int, int, int], ...] = (
    (80, 168, 8, 174, 247), (1800, 208, 3, 198, 242), (1328, 40, 9, 216, 245),
    (64, 16, 239, 16, 16), (696, 24, 250, 210, 33), (1128, 40, 189, 52, 254),
    (760, 24, 231, 193, 35), (1752, 288, 223, 233, 253), (88, 648, 250, 235, 253),
    (40, 688, 252, 254, 255), (1896, 944, 255, 252, 255), (64, 272, 254, 254, 252),
    (24, 408, 255, 254, 255), (1848, 960, 255, 254, 254), (1752, 48, 255, 255, 255),
    (376, 32, 214, 219, 222), (1552, 16, 201, 200, 200),
)
MATCH_TOL = 24              # 单通道容差
MATCH_NEED = 16             # 17 个点里至少命中这么多（成绩画面 17/17，打歌 9/17）
POLL_SEC = 0.5

#: 判定明细面板的取样矩形与它的期望均色。
#: 实测 231/235 张归档成绩图落在 (106,46,177) ±20 以内（离群的是「表示切替」另一种视图）；
#: CLEAR / 打歌 / 地图画面至少有一个通道差出 90 以上。
JUDGE_PANEL_RECT = (640, 665, 900, 845)
JUDGE_PANEL_RGB = (106, 46, 177)
JUDGE_PANEL_TOL = 45

REF_W, REF_H = 1920, 1080

CapturedFn = Callable[[str, JudgeCounts], None]
StatusFn = Callable[[str], None]
GetConfigFn = Callable[[], CunConfig]


class Frame:
    """一帧原始像素：BGRX 四字节、行优先、自上而下。"""

    __slots__ = ("buf", "width", "height")

    def __init__(self, buf: bytes, width: int, height: int) -> None:
        self.buf = buf
        self.width = width
        self.height = height

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        i = (y * self.width + x) * 4
        b, g, r = self.buf[i], self.buf[i + 1], self.buf[i + 2]
        return r, g, b

    def to_image(self) -> Image.Image:
        return Image.frombuffer(
            "RGB", (self.width, self.height), self.buf, "raw", "BGRX", 0, 1)


def grab(process_name: str) -> Frame | None:
    """抓一帧游戏客户区。游戏没跑、窗口没了或者被锁屏挡着就返回 ``None``。"""
    pid = winapi.pid_of(process_name or "chusanApp.exe")
    if pid == 0:
        return None
    hwnd = winapi.main_window_of_pid(pid)
    if not hwnd:
        return None
    rect = winapi.client_rect_on_screen(hwnd)
    if rect is None:
        return None
    x, y, w, h = rect
    if w < 640 or h < 360:
        return None                                 # 最小化了，或者是个假窗口
    buf = winapi.grab_screen(x, y, w, h)
    if buf is None:
        return None
    return Frame(buf, w, h)


def signature_score(frame: Frame) -> int:
    """17 个采样点里命中了几个。"""
    sx, sy = frame.width / REF_W, frame.height / REF_H
    hit = 0
    for x, y, r, g, b in SIGNATURE:
        px = min(int(x * sx), frame.width - 1)
        py = min(int(y * sy), frame.height - 1)
        pr, pg, pb = frame.pixel(px, py)
        if abs(pr - r) <= MATCH_TOL and abs(pg - g) <= MATCH_TOL and abs(pb - b) <= MATCH_TOL:
            hit += 1
    return hit


def judge_panel_looks_right(frame: Frame) -> bool:
    """判定明细面板那块的均色对不对得上（用来把 CLEAR 过场挡在外面）。"""
    sx, sy = frame.width / REF_W, frame.height / REF_H
    x1 = int(JUDGE_PANEL_RECT[0] * sx)
    y1 = int(JUDGE_PANEL_RECT[1] * sy)
    x2 = min(int(JUDGE_PANEL_RECT[2] * sx), frame.width)
    y2 = min(int(JUDGE_PANEL_RECT[3] * sy), frame.height)
    total_r = total_g = total_b = 0
    n = 0
    for y in range(y1, y2, 4):
        for x in range(x1, x2, 4):
            r, g, b = frame.pixel(x, y)
            total_r += r
            total_g += g
            total_b += b
            n += 1
    if n == 0:
        return False
    return (abs(total_r // n - JUDGE_PANEL_RGB[0]) <= JUDGE_PANEL_TOL
            and abs(total_g // n - JUDGE_PANEL_RGB[1]) <= JUDGE_PANEL_TOL
            and abs(total_b // n - JUDGE_PANEL_RGB[2]) <= JUDGE_PANEL_TOL)


def is_result_screen(frame: Frame) -> bool:
    return signature_score(frame) >= MATCH_NEED and judge_panel_looks_right(frame)


def save_png(frame: Frame, directory: str) -> str:
    """按截图工具的命名习惯存进截图目录，返回落盘路径。"""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = d / f"{stamp}.png"
    i = 2
    while path.exists():
        path = d / f"{stamp}_{i}.png"
        i += 1
    img = frame.to_image()
    try:
        img.save(path)
    finally:
        img.close()
    return str(path)


class CaptureService:
    """一次只跑一个截图尝试，同一首歌不重复截。"""

    def __init__(self, get_cfg: GetConfigFn, on_captured: CapturedFn, on_status: StatusFn) -> None:
        self._get_cfg = get_cfg
        self._on_captured = on_captured
        self._on_status = on_status
        self._lock = threading.Lock()
        self._busy = False
        self._last_captured: JudgeCounts | None = None
        self._stop = threading.Event()

    def shutdown(self) -> None:
        self._stop.set()

    def _status(self, msg: str) -> None:
        try:
            self._on_status(msg)
        except Exception:                           # noqa: BLE001
            pass

    def request_capture(self, final: JudgeCounts) -> None:
        """判定数冻结（结算画面出来了）时调，结算信号到达时再兜一次底。

        重复调很便宜：正在跑就直接返回，同一首歌已经截过也直接返回。
        """
        with self._lock:
            if self._stop.is_set() or self._busy or final == self._last_captured:
                return
            self._busy = True
        threading.Thread(target=self._run, args=(final,),
                         name="cun-capture", daemon=True).start()

    def _run(self, final: JudgeCounts) -> None:
        try:
            self._capture_loop(final)
        except Exception as e:                      # noqa: BLE001 - 截图失败不能带崩后台线程
            self._status(f"截图失败：{e}")
        finally:
            with self._lock:
                self._busy = False

    def _capture_loop(self, final: JudgeCounts) -> None:
        cfg = self._get_cfg()
        cap: CaptureConfig = cfg.capture
        start = time.monotonic()
        deadline = start + max(5.0, cap.timeout_s)
        best = -1
        best_frame: Frame | None = None
        chrome_but_no_panel = False                 # 指纹命中了但面板没对上

        while time.monotonic() < deadline and not self._stop.is_set():
            frame = grab(cfg.game_process)
            if frame is not None:
                score = signature_score(frame)
                panel = judge_panel_looks_right(frame)
                if score >= MATCH_NEED and not panel:
                    chrome_but_no_panel = True
                if score > best:
                    best = score
                    best_frame = frame
                if score >= MATCH_NEED and panel:
                    # chrome 出来了，但分数可能还在滚——等动画走完，复验一次，
                    # 留下**那一帧**而不是现在这帧。
                    self._stop.wait(min(max(cap.delay_s, 0.0), 15.0))
                    settled = grab(cfg.game_process)
                    if settled is not None and is_result_screen(settled):
                        path = save_png(settled, cfg.screenshots_dir)
                        with self._lock:
                            self._last_captured = final
                        elapsed = time.monotonic() - start
                        self._status(
                            f"已截取结算画面 {Path(path).name}（触发后 {elapsed:.1f}s）")
                        try:
                            self._on_captured(path, final)
                        except Exception:           # noqa: BLE001
                            pass
                        return
            self._stop.wait(POLL_SEC)

        if best < 0:
            self._status("未捕获：拿不到游戏画面（窗口不在？）")
            return

        # 把最接近的一帧存下来，方便离线看是哪几个指纹点没过、差了多少
        note = ""
        if best_frame is not None:
            try:
                d = paths.diag_dir()
                d.mkdir(parents=True, exist_ok=True)
                dump = d / f"capture_{datetime.now():%Y%m%d_%H%M%S}_best{best}.png"
                img = best_frame.to_image()
                try:
                    img.save(dump)
                finally:
                    img.close()
                note = f"，最佳帧已存 diag\\{dump.name}"
            except OSError:
                pass                                # 诊断而已，存不下就算了
        hint = "；指纹命中但判定面板未匹配（停在 CLEAR 过场/切换视图？）" if chrome_but_no_panel else ""
        self._status(f"未捕获到结算画面（超时；最高指纹得分 {best}/{len(SIGNATURE)}{hint}{note}）")
