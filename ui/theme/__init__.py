# -*- coding: utf-8 -*-
"""主题入口。业务代码只跟这个模块打交道：``from . import theme``。

四个模块分工：

- :mod:`~ui.theme.tokens`  固化的语义色板，纯数据、不依赖 Qt
- :mod:`~ui.theme.metrics` 字号 / 间距 / 圆角 / 动效 / 阴影，同样纯数据
- :mod:`~ui.theme.qss`     语义 Token → QSS，唯一拼样式表的地方
- 本文件                    当前模式、取色、取字体、系统设置的接入

业务组件只消费语义 Token，不散写 Hex、字号、间距、圆角、阴影与动画时长。

深浅两套是两份独立映射，不是反色。模式来自配置里的 ``appearance``
（``system`` / ``light`` / ``dark``），跟随系统时读 Qt 的 ``colorScheme()``。
"""

from __future__ import annotations

import html

from PySide6.QtCore import QEasingCurve, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from core import winapi

from . import metrics as m
from . import qss as _qss
from . import tokens as _tokens
from .metrics import (BODY, BUTTON, CAPTION, METRIC, MONO, PAGE_TITLE, SECONDARY,
                      SECTION_TITLE, TITLE, FontSpec)

# 常用度量直接 re-export，页面里写 theme.GAP_SECTION 而不是 theme.metrics.GAP_SECTION
from .metrics import (CARD_TO_NOTE, COLUMN_WIDTH, EASE_EXIT, EASE_STANDARD,  # noqa: F401
                      FOCUS_RING_INNER_WIDTH, FOCUS_RING_OFFSET, FOCUS_RING_WIDTH,
                      GAP_CONTROL, GAP_GROUP, GAP_INLINE, GAP_RELATED, GAP_SECTION,
                      ICON_ACTION, ICON_INLINE, LAYER_TOAST, MOTION_IMMEDIATE,
                      MOTION_LARGE, MOTION_MEDIUM, MOTION_REDUCED_FADE,
                      MOTION_REDUCED_MOVE, MOTION_SMALL, PADDING_CONTAINER,
                      PADDING_CONTROL_X, PADDING_CONTROL_Y, PADDING_PAGE_X,
                      PADDING_PAGE_Y, PAGE_TITLE_TO_SECTION, RADIUS_LARGE,
                      RADIUS_MEDIUM, RADIUS_SMALL, ROW_MIN_HEIGHT,
                      ROW_WITH_SUBLABEL_MIN_HEIGHT, SECTION_TITLE_TO_CARD, SPACE_1,
                      SPACE_2, SPACE_3, SPACE_4, SPACE_5, SPACE_6, SPACE_8,
                      SPACE_10, TOOLTIP_MAX_WIDTH)
from .tokens import DESIGN_SYSTEM_REVISION, VIZ_CATEGORICAL_COUNT  # noqa: F401

#: 配置里 ``appearance`` 的三个取值
APPEARANCE_SYSTEM, APPEARANCE_LIGHT, APPEARANCE_DARK = "system", "light", "dark"
APPEARANCES = (APPEARANCE_SYSTEM, APPEARANCE_LIGHT, APPEARANCE_DARK)
APPEARANCE_LABELS = {APPEARANCE_SYSTEM: "跟随系统",
                     APPEARANCE_LIGHT: "浅色",
                     APPEARANCE_DARK: "深色"}

_appearance = APPEARANCE_SYSTEM
_dark = True
_scale = 1.0
_families: list[str] | None = None
_mono_families: list[str] | None = None

_CJK_FALLBACK = ("Microsoft YaHei UI", "微软雅黑", "PingFang SC", "Noto Sans CJK SC")
_MONO_FALLBACK = ("Cascadia Mono", "Consolas", "Microsoft YaHei UI", "微软雅黑")


# ----------------------------- 模式 -----------------------------------------
def system_prefers_dark() -> bool:
    """系统当前是不是深色。

    Qt 6.5 起 ``QStyleHints.colorScheme()`` 直接给答案，还带变更信号；
    拿不到就退回读注册表。两条都失败时按深色处理——本程序在游戏旁边跑，
    深色是更安全的默认。
    """
    app = QGuiApplication.instance()
    if app is not None:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Light:
            return False
        if scheme == Qt.ColorScheme.Dark:
            return True
    light = winapi.apps_use_light_theme()
    return True if light is None else not light


def set_appearance(value: str) -> bool:
    """按配置值定下当前模式。返回模式是否发生了变化。"""
    global _appearance, _dark
    _appearance = value if value in APPEARANCES else APPEARANCE_SYSTEM
    dark = {APPEARANCE_LIGHT: False, APPEARANCE_DARK: True}.get(
        _appearance, None)
    if dark is None:
        dark = system_prefers_dark()
    changed = dark != _dark
    _dark = dark
    return changed


def appearance() -> str:
    return _appearance


def is_dark() -> bool:
    return _dark


def follows_system() -> bool:
    return _appearance == APPEARANCE_SYSTEM


def palette() -> dict[str, str]:
    return _tokens.DARK if _dark else _tokens.LIGHT


# ----------------------------- 取色 -----------------------------------------
def color(key: str) -> str:
    """语义 Token → ``#rrggbb``。给 QSS 和需要字符串的地方用。

    拼错键名要当场炸，不能静默返回空串——那会变成「界面塌了但什么都不报」。
    """
    return palette()[key]


def qcolor(key: str) -> QColor:
    """语义 Token → :class:`QColor`。给自绘控件用。"""
    return QColor(palette()[key])


def viz_series(index: int) -> str:
    """分类色板按序取用。顺序固定，同一份数据在哪都同色同序。"""
    return color(f"viz.categorical.{index % _tokens.VIZ_CATEGORICAL_COUNT + 1}")


# ----------------------------- 字体 -----------------------------------------
def _resolve_families() -> None:
    """系统界面字体打头，后面挂中文兜底。

    规范要求普通 UI **继承用户当前的系统界面字体**，不擅自替换字体类别，
    所以第一顺位取系统字体而不是写死 Segoe UI。后面那几个只是兜底：
    Segoe UI 没有汉字字形，不挂兜底的话中文走系统默认回退、行高和西文对不齐。

    ``setFamilies`` 让 Qt **逐字符**回退，西文用系统字体、汉字用雅黑，
    两边的字号和基线仍然一致。别写成「挑第一个装了的家族」。
    """
    global _families, _mono_families
    try:
        ui_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
        mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    except (RuntimeError, AttributeError):          # 没有 QGuiApplication
        ui_family = mono_family = ""
    _families = [f for f in (ui_family, *_CJK_FALLBACK) if f]
    _mono_families = [f for f in (mono_family, *_MONO_FALLBACK) if f]


def refresh_system_metrics() -> None:
    """重新读一次系统的文本缩放。切换主题或系统设置变化时调。"""
    global _scale
    _scale = winapi.text_scale_factor()
    _resolve_families()


def _qt_weight(css_weight: int) -> QFont.Weight:
    return {400: QFont.Weight.Normal,
            500: QFont.Weight.Medium,
            600: QFont.Weight.DemiBold}.get(css_weight, QFont.Weight.Normal)


def font(spec: FontSpec = BODY, mono: bool = False) -> QFont:
    """按排版角色取字体。

    ``spec.size`` 是**逻辑**像素，Qt 6 的高 DPI 缩放会自己处理显示缩放。
    Windows 辅助功能里的「放大文本」是另一个设置，Qt 不管，所以在这里乘一次
    ——规范要求系统字体缩放只由框架应用一次，这就是那一次。
    """
    if _families is None:
        _resolve_families()
    f = QFont()
    f.setFamilies(list(_mono_families if mono else _families))
    f.setPixelSize(max(1, round(spec.size * _scale)))
    f.setWeight(_qt_weight(spec.weight))
    return f


def line_height(spec: FontSpec) -> int:
    """角色的行高，同样跟着系统文本缩放走。"""
    return max(1, round(spec.line_height * _scale))


def scaled(value: int) -> int:
    """让一个跟着文字走的尺寸（行高地板之类）跟着文本缩放。

    纯布局间距**不**用这个：规范说系统字体缩放只应用于字体，间距靠自适应布局
    容纳变大的文字，不是把整个界面等比放大。
    """
    return max(1, round(value * _scale))


def rich_text(text: str, spec: FontSpec) -> str:
    """把会换行的文本包一层富文本，设定行高。

    Qt 的 QSS 不认 ``line-height``，但富文本引擎认（实测：200px 宽的标签
    从 26 高变成 56 高）。单行标签不需要这层——高度由字号决定。

    文本一律转义：路径里的 ``&`` 不转义会被当成 HTML 实体吃掉。
    """
    return (f'<div style="line-height:{line_height(spec)}px">'
            f'{html.escape(text)}</div>')


# ----------------------------- 动效 -----------------------------------------
def duration(base: int, moves: bool = True) -> int:
    """动画时长。系统开了「减少动态效果」就按规范降级。

    位移与缩放降到 0；颜色和透明度统一 100ms，保留即时而清晰的状态反馈。
    """
    if winapi.animations_enabled():
        return base
    return m.MOTION_REDUCED_MOVE if moves else m.MOTION_REDUCED_FADE


def easing(exit_curve: bool = False) -> QEasingCurve:
    """规范的两条缓动：进入 / 状态变化用标准曲线，离场用退出曲线。"""
    p1, p2 = m.EASE_EXIT if exit_curve else m.EASE_STANDARD
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(*p1), QPointF(*p2), QPointF(1.0, 1.0))
    return curve


# ----------------------------- 阴影 -----------------------------------------
def apply_shadow(widget: QWidget, shadow: m.Shadow = m.ELEVATION_2) -> QGraphicsDropShadowEffect:
    """把结构化阴影 Token 落到 Qt 上：``blurRadius = blur``、``offset = (x, y)``。

    Qt 没有 spread 的概念，Token 里那一项保持 0。
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(shadow.blur)
    effect.setOffset(shadow.x, shadow.y)
    effect.setColor(_rgba(shadow.dark if _dark else shadow.light))
    widget.setGraphicsEffect(effect)
    return effect


def _rgba(spec: str) -> QColor:
    """``rgba(r, g, b, a)`` → :class:`QColor`。Token 里的阴影和 scrim 是这个形式。"""
    body = spec[spec.index("(") + 1:spec.rindex(")")]
    parts = [p.strip() for p in body.split(",")]
    c = QColor(int(parts[0]), int(parts[1]), int(parts[2]))
    c.setAlphaF(float(parts[3]))
    return c


# ----------------------------- 样式表 ---------------------------------------
def stylesheet(mica: bool = False) -> str:
    """当前模式下的整份样式表。挂在 QApplication 上。"""
    return _qss.build(palette(), mica)


def apply(app, mica: bool = False) -> None:
    """把字体和样式表一起装上。切换深浅、切换材质回退都走这里。"""
    refresh_system_metrics()
    app.setFont(font(BODY))
    app.setStyleSheet(stylesheet(mica))


__all__ = [
    "APPEARANCES", "APPEARANCE_DARK", "APPEARANCE_LABELS", "APPEARANCE_LIGHT",
    "APPEARANCE_SYSTEM", "BODY", "BUTTON", "CAPTION", "DESIGN_SYSTEM_REVISION",
    "METRIC", "MONO", "PAGE_TITLE", "SECONDARY", "SECTION_TITLE", "TITLE",
    "FontSpec", "appearance", "apply", "apply_shadow", "color", "duration",
    "easing", "follows_system", "font", "is_dark", "line_height", "palette",
    "qcolor", "refresh_system_metrics", "rich_text", "scaled", "set_appearance",
    "stylesheet", "system_prefers_dark", "viz_series",
]
