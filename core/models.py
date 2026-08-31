# -*- coding: utf-8 -*-
"""``cun_config.json`` 的强类型镜像，以及在各模块之间传递的小结构。

JSON 的键名一律 snake_case，与 v1.x 完全一致——老配置文件直接读得动，
新版写回去 v1.x 也还认得。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NamedTuple

#: 满分
MAX_SCORE = 1_010_000

DEFAULT_RANK_THRESHOLDS: dict[str, int] = {
    "SSS+": 1009000, "SSS": 1007500, "SS+": 1005000, "SS": 1000000,
    "S+": 990000, "S": 975000, "AAA": 950000, "AA": 925000, "A": 900000,
    "BBB": 800000, "BB": 700000, "B": 600000, "C": 500000, "D": 0,
}

DEFAULT_BOXES: dict[str, list[int]] = {
    "top_line1": [558, 6, 1345, 40],
    "top_line2": [760, 42, 1345, 82],
    "bd_atk": [824, 758, 921, 792],
    "bd_miss": [824, 806, 921, 840],
}

#: 整理维度的规范顺序，配置里缺哪个就按这个补
ORGANIZE_KINDS = ("date", "rank", "achievement")


class JudgeCounts(NamedTuple):
    """从游戏内存读到的一次判定计数快照。"""

    critical: int = 0
    justice: int = 0
    attack: int = 0
    miss: int = 0

    @property
    def total(self) -> int:
        return self.critical + self.justice + self.attack + self.miss

    @property
    def score(self) -> int:
        """CHUNITHM 没有连击加成，得分完全由判定权重决定。

        每个 note 值 ``1,000,000 / 物量``，JC 付 101%、JUSTICE 100%、ATTACK 50%、
        MISS 0，全 JC 即 1,010,000。

        ⚠️ **向下取整，不是四舍五入。** 拿 120 张真实结算截图对过：顶栏的四个
        判定数按上面的公式算出来，截断值有 119 次和画面上显示的得分**完全相同**，
        四舍五入则有 54 次高出 1 分。v1.x（C# 版）用的是 ``Math.Round``，所以
        联动那条路换算出来的分数会系统性偏高 1，在评级边界上会改判
        （1,007,500 是 SSS，1,007,499 只是 SS+）。

        ⚠️ **必须用整数算。** 走浮点的话本该整除的值会落成 ``1009989.9999…``，
        截断之后又少 1——这正是「换成截断」最容易引进的新 bug。
        把权重乘 100 变成整数（101 / 100 / 50 / 0）就没有误差了。
        """
        if self.total == 0:
            return 0
        weighted = 101 * self.critical + 100 * self.justice + 50 * self.attack
        return 1_000_000 * weighted // (100 * self.total)


@dataclass
class OcrRecord:
    """一张截图的判定数据。缓存文件 ``cun_ocr_cache.json`` 存的就是它。"""

    score: int | None = None
    attack: int | None = None
    miss: int | None = None
    #: OCR 当时的文件字节数。缓存按文件名索引，同名不同文件靠它区分；
    #: 老版本写的记录没有这个字段（None），当作匹配处理。
    size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"score": self.score, "attack": self.attack, "miss": self.miss}
        if self.size is not None:
            d["size"] = self.size
        return d

    @classmethod
    def from_dict(cls, d: Any) -> "OcrRecord":
        if not isinstance(d, dict):
            return cls()
        return cls(
            score=_opt_int(d.get("score")),
            attack=_opt_int(d.get("attack")),
            miss=_opt_int(d.get("miss")),
            size=_opt_int(d.get("size")),
        )


@dataclass
class OcrResult:
    """一次识别的完整产物，比缓存记录多几个只给日志和排查看的字段。"""

    file: str = ""
    path: str = ""
    score: int | None = None
    attack: int | None = None
    miss: int | None = None
    rank: str | None = None
    note: str = ""
    raw_line1: str = ""
    raw_line2: str = ""

    def to_record(self, size: int | None = None) -> OcrRecord:
        return OcrRecord(score=self.score, attack=self.attack, miss=self.miss, size=size)


@dataclass
class Category:
    """一条判定规则（配置页里的一行）。"""

    key: str = ""
    label: str = ""
    kind: str = ""          # score | ajcun | am | aj | fc
    enabled: bool = False
    folder: str = ""
    custom: bool = False
    lo: int | None = None
    hi: int | None = None
    m_hi: int | None = None
    a_hi: int | None = None
    min_rank: str | None = None
    score_min: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": self.key, "label": self.label, "kind": self.kind,
            "enabled": self.enabled, "folder": self.folder,
        }
        if self.custom:
            d["custom"] = True
        for name in ("lo", "hi", "m_hi", "a_hi", "min_rank", "score_min"):
            v = getattr(self, name)
            if v is not None:
                d[name] = v
        return d

    @classmethod
    def from_dict(cls, d: Any) -> "Category":
        if not isinstance(d, dict):
            return cls()
        return cls(
            key=str(d.get("key", "")),
            label=str(d.get("label", "")),
            kind=str(d.get("kind", "")),
            enabled=bool(d.get("enabled", False)),
            folder=str(d.get("folder", "")),
            custom=bool(d.get("custom", False)),
            lo=_opt_int(d.get("lo")),
            hi=_opt_int(d.get("hi")),
            m_hi=_opt_int(d.get("m_hi")),
            a_hi=_opt_int(d.get("a_hi")),
            min_rank=d.get("min_rank") if isinstance(d.get("min_rank"), str) else None,
            score_min=_opt_int(d.get("score_min")),
        )


@dataclass
class OrganizeStep:
    """一个整理维度。列表里的顺序就是文件夹的嵌套顺序，靠前＝外层。"""

    kind: str = ""                  # date | rank | achievement
    enabled: bool = False
    date_span: str = "month"        # year | month | day

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "enabled": self.enabled, "date_span": self.date_span}

    @classmethod
    def from_dict(cls, d: Any) -> "OrganizeStep":
        if not isinstance(d, dict):
            return cls()
        span = d.get("date_span")
        return cls(
            kind=str(d.get("kind", "")),
            enabled=bool(d.get("enabled", False)),
            date_span=span if span in ("year", "month", "day") else "month",
        )


@dataclass
class OrganizeConfig:
    steps: list[OrganizeStep] = field(default_factory=lambda: [
        OrganizeStep(kind="date"), OrganizeStep(kind="rank"), OrganizeStep(kind="achievement"),
    ])

    def to_dict(self) -> dict[str, Any]:
        return {"steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, d: Any) -> "OrganizeConfig":
        if not isinstance(d, dict):
            return cls()
        raw = d.get("steps")
        if not isinstance(raw, list):
            return cls()
        return cls(steps=[OrganizeStep.from_dict(s) for s in raw])


@dataclass
class DgHubConfig:
    """cun 这一侧的联动设置：只有开关和数据端口。

    触发行为（波形预设、强度、通道、时长）在 DGHub 插件自己的配置页里，
    cun 只负责把判定数据和结算的寸判定发出去。
    """

    enabled: bool = False
    port: int = 8890            # 8888 是 Chuni2Api 的

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "port": self.port}

    @classmethod
    def from_dict(cls, d: Any) -> "DgHubConfig":
        if not isinstance(d, dict):
            return cls()
        return cls(enabled=bool(d.get("enabled", False)), port=_int(d.get("port"), 8890))


@dataclass
class CaptureConfig:
    """自动截取结算画面。依赖内存读取，本开关或 DGHub 联动任一开启即运行。"""

    enabled: bool = False
    #: 认出结算画面后等几秒再存，让分数滚动动画走完
    delay_s: float = 2.5
    #: 一首歌结束后等这么久还没等到结算画面就放弃
    timeout_s: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "delay_s": self.delay_s, "timeout_s": self.timeout_s}

    @classmethod
    def from_dict(cls, d: Any) -> "CaptureConfig":
        if not isinstance(d, dict):
            return cls()
        return cls(
            enabled=bool(d.get("enabled", False)),
            delay_s=_float(d.get("delay_s"), 2.5),
            timeout_s=_float(d.get("timeout_s"), 30.0),
        )


@dataclass
class CunConfig:
    """``cun_config.json`` 的全部内容。"""

    #: CHUNITHM 游戏根目录（安装向导 / 首次运行向导写入）。
    #: 截图目录和 start.bat 留空时从它推导。
    game_root: str = ""
    screenshots_dir: str = ""
    output_root: str = ""
    cun_folder: str = "寸"
    aj_folder: str = "AJ"
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    process_mode: str = "realtime"
    game_process: str = "chusanApp.exe"
    game_poll_sec: float = 4.0
    game_exit_grace_sec: float = 20.0
    rename_with_stats: bool = True
    expected_size: list[int] = field(default_factory=lambda: [1920, 1080])
    dark_threshold: int = 95
    bright_threshold: int = 110
    boxes: dict[str, list[int]] = field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_BOXES.items()})
    rank_thresholds: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_RANK_THRESHOLDS))
    categories: list[Category] = field(default_factory=list)
    organize: OrganizeConfig = field(default_factory=OrganizeConfig)
    dghub: DgHubConfig = field(default_factory=DgHubConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    #: 已接入自启动行的 start.bat 路径（空＝从没配过）。
    #: 当前是否真的接入以 bat 文件内容为准，两者不会各说各话。
    start_bat: str = ""
    #: 界面外观：``system`` 跟随系统 / ``light`` 浅色 / ``dark`` 深色。
    #: 老配置没有这个键，读出来就是默认的跟随系统。
    appearance: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_root": self.game_root,
            "screenshots_dir": self.screenshots_dir,
            "output_root": self.output_root,
            "cun_folder": self.cun_folder,
            "aj_folder": self.aj_folder,
            "tesseract_cmd": self.tesseract_cmd,
            "process_mode": self.process_mode,
            "game_process": self.game_process,
            "game_poll_sec": self.game_poll_sec,
            "game_exit_grace_sec": self.game_exit_grace_sec,
            "rename_with_stats": self.rename_with_stats,
            "expected_size": list(self.expected_size),
            "dark_threshold": self.dark_threshold,
            "bright_threshold": self.bright_threshold,
            "boxes": {k: list(v) for k, v in self.boxes.items()},
            "rank_thresholds": dict(self.rank_thresholds),
            "categories": [c.to_dict() for c in self.categories],
            "organize": self.organize.to_dict(),
            "dghub": self.dghub.to_dict(),
            "capture": self.capture.to_dict(),
            "start_bat": self.start_bat,
            "appearance": self.appearance,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "CunConfig":
        cfg = cls()
        if not isinstance(d, dict):
            return cfg
        cfg.game_root = _str(d.get("game_root"), cfg.game_root)
        cfg.screenshots_dir = _str(d.get("screenshots_dir"), cfg.screenshots_dir)
        cfg.output_root = _str(d.get("output_root"), cfg.output_root)
        cfg.cun_folder = _str(d.get("cun_folder"), cfg.cun_folder)
        cfg.aj_folder = _str(d.get("aj_folder"), cfg.aj_folder)
        cfg.tesseract_cmd = _str(d.get("tesseract_cmd"), cfg.tesseract_cmd)
        cfg.process_mode = _str(d.get("process_mode"), cfg.process_mode)
        cfg.game_process = _str(d.get("game_process"), cfg.game_process)
        cfg.game_poll_sec = _float(d.get("game_poll_sec"), cfg.game_poll_sec)
        cfg.game_exit_grace_sec = _float(d.get("game_exit_grace_sec"), cfg.game_exit_grace_sec)
        cfg.rename_with_stats = bool(d.get("rename_with_stats", cfg.rename_with_stats))
        size = d.get("expected_size")
        if isinstance(size, list) and len(size) == 2:
            cfg.expected_size = [_int(size[0], 1920), _int(size[1], 1080)]
        cfg.dark_threshold = _int(d.get("dark_threshold"), cfg.dark_threshold)
        cfg.bright_threshold = _int(d.get("bright_threshold"), cfg.bright_threshold)

        boxes = d.get("boxes")
        if isinstance(boxes, dict):
            for k, v in boxes.items():
                if isinstance(v, list) and len(v) == 4:
                    cfg.boxes[str(k)] = [_int(x, 0) for x in v]

        thr = d.get("rank_thresholds")
        if isinstance(thr, dict) and thr:
            cfg.rank_thresholds = {str(k): _int(v, 0) for k, v in thr.items()}

        cats = d.get("categories")
        if isinstance(cats, list):
            cfg.categories = [Category.from_dict(c) for c in cats]

        cfg.organize = OrganizeConfig.from_dict(d.get("organize"))
        cfg.dghub = DgHubConfig.from_dict(d.get("dghub"))
        cfg.capture = CaptureConfig.from_dict(d.get("capture"))
        cfg.start_bat = _str(d.get("start_bat"), cfg.start_bat)
        appearance = _str(d.get("appearance"), cfg.appearance)
        cfg.appearance = appearance if appearance in ("system", "light", "dark") else "system"
        return cfg


@dataclass
class ScanResult:
    total: int = 0
    cun: int = 0
    aj: int = 0
    error: str | None = None


# ----------------------------- 小工具 ---------------------------------------
def _opt_int(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any, fallback: int) -> int:
    got = _opt_int(v)
    return fallback if got is None else got


def _float(v: Any, fallback: float) -> float:
    if v is None or isinstance(v, bool):
        return fallback
    try:
        return float(v)
    except (TypeError, ValueError):
        return fallback


def _str(v: Any, fallback: str) -> str:
    return v if isinstance(v, str) else fallback
