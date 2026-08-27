# -*- coding: utf-8 -*-
"""结算截图的 OCR。

读的是结算画面顶部状态栏那行清晰的等宽字，不碰中间那串彩虹大字：
把深色描边隔离出来，白色的 ``SCORE / ATTACK / MISS`` 就变成干净的黑白图，
再交给 Tesseract。

一张图正常只跑**一次** tesseract 进程：两行顶栏合成一个 list file 一起识别
（同一个 psm），只有解析不出来时才追加调用。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PIL import Image, ImageOps

from . import config as config_mod
from . import paths
from .models import CunConfig, OcrResult

#: 顶栏两行用整行模式，判定明细那两个小框是单个词
PSM_SINGLE_LINE = 7
PSM_SINGLE_BLOCK = 6
PSM_SINGLE_WORD = 8

#: 顶栏那一行两边补的留白（像素，作用在放大 4 倍之后的图上）。
#: **只给顶栏用**：第二行（得分）补了留白之后 psm 7 会整行读空，
#: 在 303 张真实截图上实测多出 115 处得分错误。
TOP_LINE_PAD = 20

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_SCORE_TOKEN_RE = re.compile(r"[\d,]+")
_GAP_RE = re.compile(r"(?<=[\d,])\s+(?=[\d,])")
_NON_DIGIT_RE = re.compile(r"\D")


class OcrEngine:
    """一个可复用的识别器。线程安全（内部一把锁），用完调 :meth:`close`。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tmp: Path | None = None

    # ----------------------------- 生命周期 ---------------------------------
    def close(self) -> None:
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

    def __enter__(self) -> "OcrEngine":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _tmp_dir(self) -> Path:
        if self._tmp is None:
            self._tmp = Path(tempfile.mkdtemp(prefix="cun-ocr-"))
        return self._tmp

    # ----------------------------- 引擎定位 ---------------------------------
    @staticmethod
    def tesseract_exe(cfg: CunConfig) -> str | None:
        """要跑的 tesseract.exe；装都没装就返回 ``None``。"""
        if cfg.tesseract_cmd and Path(cfg.tesseract_cmd).is_file():
            return cfg.tesseract_cmd
        return shutil.which("tesseract")

    @staticmethod
    def tessdata_dir(cfg: CunConfig) -> Path | None:
        """需要显式指定的 ``tessdata`` 目录。

        Tesseract 自己会找 exe 旁边那份，所以那种情况返回 ``None``（不加参数）；
        只有语言包被放在数据目录里时才要 ``--tessdata-dir``。
        """
        exe = OcrEngine.tesseract_exe(cfg)
        if exe:
            beside = Path(exe).parent / "tessdata"
            if (beside / "eng.traineddata").is_file():
                return None
        local = paths.data_dir() / "tessdata"
        if (local / "eng.traineddata").is_file():
            return local
        return None

    @staticmethod
    def available(cfg: CunConfig) -> bool:
        return OcrEngine.tesseract_exe(cfg) is not None

    # ----------------------------- 识别 -------------------------------------
    def detect(self, path: str | Path, cfg: CunConfig) -> OcrResult:
        """识别一张结算截图。任何失败都写进 ``note``，不抛异常。"""
        p = Path(path)
        out = OcrResult(file=p.name, path=str(p))

        exe = self.tesseract_exe(cfg)
        if exe is None:
            out.note = "ocr_engine_unavailable"
            return out

        try:
            with Image.open(p) as raw:
                img = raw.convert("RGB")
        except (OSError, ValueError) as e:
            out.note = f"open_failed: {e}"
            return out

        w, h = img.size
        exp = cfg.expected_size
        boxes = cfg.boxes
        dark_th, bright_th = cfg.dark_threshold, cfg.bright_threshold

        with self._lock:
            line1_img = _prep_region(img, _scaled_box(boxes["top_line1"], w, h, exp),
                                     dark_th, True, pad=TOP_LINE_PAD)
            line2_img = _prep_region(img, _scaled_box(boxes["top_line2"], w, h, exp),
                                     dark_th, True)
            try:
                texts = self._ocr(exe, cfg, [line1_img, line2_img], PSM_SINGLE_LINE)
                t1 = texts[0] if len(texts) > 0 else ""
                t2 = texts[1] if len(texts) > 1 else ""
                out.raw_line1, out.raw_line2 = t1, t2

                # ATTACK / MISS：顶栏有标签⟺≥1，没标签⟺0（游戏把 0 的项整个隐藏了）
                upper = t1.upper()
                attack, asrc = _top_field(upper, "ATTACK", t1, r"ATTACK\D{0,4}(\d{1,4})")
                miss, msrc = _top_field(upper, "MISS", t1, r"MISS\D{0,4}(\d{1,4})")

                score = _parse_score(t2)
                if score is None:
                    # 第二行还要再喂一次，所以 _ocr 不能把图关掉，生命周期在这里管
                    t2b = self._ocr(exe, cfg, [line2_img], PSM_SINGLE_BLOCK)[0]
                    s2 = _parse_score(t2b)
                    if s2 is not None:
                        score = s2
                        out.raw_line2 = f"{t2} || psm6:{t2b}"

                notes: list[str] = []
                if asrc == "unread":
                    bd = self._breakdown(exe, cfg, img, boxes["bd_atk"], w, h, exp, bright_th)
                    if bd is not None:
                        attack = bd
                        notes.append("attack_from_breakdown")
                if msrc == "unread":
                    bd = self._breakdown(exe, cfg, img, boxes["bd_miss"], w, h, exp, bright_th)
                    if bd is not None:
                        miss = bd
                        notes.append("miss_from_breakdown")
            finally:
                line1_img.close()
                line2_img.close()

        img.close()
        out.score = score
        out.attack = attack
        out.miss = miss
        out.rank = config_mod.rank_of(score, cfg)
        out.note = ";".join(notes)
        return out

    def _breakdown(self, exe: str, cfg: CunConfig, img: Image.Image, box: list[int],
                   w: int, h: int, exp: list[int], threshold: int) -> int | None:
        """顶栏那一项读不出来时，退回判定明细面板里的小数字。"""
        region = _prep_region(img, _scaled_box(box, w, h, exp), threshold, False)
        try:
            text = self._ocr(exe, cfg, [region], PSM_SINGLE_WORD, whitelist="0123456789")[0]
        finally:
            region.close()
        return _find_int(r"(\d{1,4})", text, 0, 9999)

    def _ocr(self, exe: str, cfg: CunConfig, images: list[Image.Image], psm: int,
             whitelist: str | None = None) -> list[str]:
        """把几张已经预处理好的图交给一次 tesseract 调用，返回每张的文本。

        **不负责关图**：同一张图可能要换个 psm 再喂一次，关掉了下一次就炸。
        """
        tmp = self._tmp_dir()
        files: list[Path] = []
        for i, im in enumerate(images):
            f = tmp / f"region{i}.png"
            im.save(f)
            files.append(f)

        if len(files) == 1:
            target = str(files[0])
        else:
            listing = tmp / "batch.txt"
            listing.write_text("\n".join(str(f) for f in files), encoding="utf-8")
            target = str(listing)

        cmd = [exe, target, "stdout", "-l", "eng", "--psm", str(psm)]
        tessdata = self.tessdata_dir(cfg)
        if tessdata is not None:
            cmd += ["--tessdata-dir", str(tessdata)]
        if whitelist:
            cmd += ["-c", f"tessedit_char_whitelist={whitelist}"]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=60,
                creationflags=_CREATE_NO_WINDOW, check=False)
        except (OSError, subprocess.SubprocessError):
            return [""] * len(files)

        text = proc.stdout.decode("utf-8", errors="replace")
        pages = text.split("\f")
        return [(pages[i].strip() if i < len(pages) else "") for i in range(len(files))]


# ----------------------------- 图像预处理 -----------------------------------
def _scaled_box(box: list[int], w: int, h: int, exp: list[int]) -> tuple[int, int, int, int]:
    """把按 1920×1080 标定的框换算到实际分辨率。"""
    if w == exp[0] and h == exp[1]:
        return box[0], box[1], box[2], box[3]
    sx, sy = w / exp[0], h / exp[1]
    return int(box[0] * sx), int(box[1] * sy), int(box[2] * sx), int(box[3] * sy)


def _prep_region(img: Image.Image, box: tuple[int, int, int, int],
                 threshold: int, dark_below: bool, scale: int = 4,
                 pad: int = 0) -> Image.Image:
    """裁剪 → 放大 4 倍 → 灰度 → 二值化（可选补一圈背景色留白）。

    ``dark_below=True`` 是顶栏模式（亮度低于阈值的变黑，也就是把深色描边留下来）；
    ``False`` 是判定明细模式（亮度高于阈值的变黑）。
    """
    left, top, right, bottom = box
    left = max(0, min(left, img.width))
    top = max(0, min(top, img.height))
    right = max(left + 1, min(right, img.width))
    bottom = max(top + 1, min(bottom, img.height))

    crop = img.crop((left, top, right, bottom))
    crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.BICUBIC)
    gray = crop.convert("L")            # PIL 的 L 就是 ITU-R 601-2，和 C# 那版同一条公式
    crop.close()
    binary = gray.point((lambda p: 0 if p < threshold else 255) if dark_below
                        else (lambda p: 0 if p > threshold else 255))
    if pad > 0:
        # 边缘那一圈背景色。数字紧贴右边界时，tesseract 会把边缘噪点连上去
        # ——实测「MISS : 1」被读成「14」，7 张真实截图上都是这样。
        binary = ImageOps.expand(binary, pad, 0 if dark_below else 255)
    return binary


# ----------------------------- 文本解析 -------------------------------------
def _parse_score(text: str) -> int | None:
    """从一行文本里挑出得分。取合法范围内最大的那个数。"""
    text = _GAP_RE.sub("", text)        # 「1,007 ,603」这种被 OCR 塞进去的空格
    best: int | None = None
    for token in _SCORE_TOKEN_RE.findall(text):
        digits = _NON_DIGIT_RE.sub("", token)
        if not 6 <= len(digits) <= 7:
            continue
        try:
            v = int(digits)
        except ValueError:
            continue
        if 100_000 <= v <= 1_010_000 and (best is None or v > best):
            best = v
    return best


def _find_int(pattern: str, text: str, lo: int | None = None, hi: int | None = None) -> int | None:
    for m in re.finditer(pattern, text, re.IGNORECASE):
        try:
            v = int(m.group(1))
        except (IndexError, ValueError):
            continue
        if (lo is None or v >= lo) and (hi is None or v <= hi):
            return v
    return None


def _top_field(upper: str, label: str, raw: str, pattern: str) -> tuple[int | None, str]:
    """顶栏某一项的值和它的来源。

    返回 ``(值, 来源)``，来源是 ``zero``（标签根本没出现＝该项为 0）、
    ``top``（顶栏读到了）或 ``unread``（有标签但数字没读出来，调用方去查明细面板）。
    """
    if label not in upper:
        return 0, "zero"
    m = re.search(pattern, raw, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1)), "top"
        except ValueError:
            pass
    return None, "unread"
