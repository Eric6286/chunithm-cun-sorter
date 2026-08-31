# -*- coding: utf-8 -*-
"""固化的语义色板。**纯数据，不 import PySide6。**

不依赖 Qt 是有意的：对比度测试可以直接算，不用起 QApplication；换项目时
也只需要替换这一个文件。

色值来自 `~\\Workspace\\lab\\设计系统重做` 的离线生成器，经人工校准后固化。
**运行时不导入那个工具，也不读它的 out/。** 算法是设计工具，不是运行时真理。

品牌方向：杏桃橙（OKLCH Hue 55）。Light 与 Dark 是两套独立映射，不是反色：
Light 的 ``accent.text`` 是深橙 ``#A35200``，Dark 的直接等于 ``accent.primary``。

⚠️ **两套的键集合必须完全一致。** 少一个键就是那个模式下 KeyError，或者更糟——
QSS 里静默变成空串，界面塌掉却不报错。``tests/test_theme.py`` 钉着这条。
"""

from __future__ import annotations

#: 本项目遵循的全局规范版本。跨项目视觉对比只在这个值一致时才成立。
DESIGN_SYSTEM_REVISION = "2026.08.31-a11y-baseline"

#: 品牌 Seed。只描述色彩身份，不直接作为 UI 颜色。
BRAND_HUE = 55.0
BRAND_CHROMA = 0.135

#: 文字承载面：每个文字 Token 都要在这些面上逐一达到对比度门槛，
#: 不是只对 ``canvas`` 校验一次。
TEXT_BEARING_SURFACES = (
    "canvas", "surface", "surfaceElevated", "surfaceSunken", "fill.control",
    "accent.subtle",
    "semantic.success.subtle", "semantic.warning.subtle",
    "semantic.error.subtle", "semantic.info.subtle",
)

#: 不在保证集合内的面。规范明确：这些面上不使用 ``text.tertiary``，
#: 整行 Hover / Pressed 时行内辅助文字提升为 ``text.secondary``。
UNGUARANTEED_SURFACES = ("fill.hover", "fill.pressed", "accent.subtleHover")

LIGHT: dict[str, str] = {
    # --- Neutral：面 ---
    "canvas": "#FFF9F5",
    "surface": "#FFFEFE",
    "surfaceElevated": "#FFFFFF",
    "surfaceSunken": "#F6F0EC",
    # --- Neutral：文字 ---
    "text.primary": "#1E1A17",
    "text.secondary": "#534F4C",
    "text.tertiary": "#6C6764",
    "text.disabled": "#96918E",
    "text.inverse": "#F6F0ED",
    # --- Neutral：分隔、边界、填充 ---
    "separator.subtle": "#DAD4D0",
    "separator.strong": "#BCB7B3",
    "border.default": "#7E7976",
    "fill.control": "#ECE7E3",
    "fill.hover": "#E2DDD9",
    "fill.pressed": "#D8D2CE",
    "scrim": "rgba(30, 26, 23, 0.32)",
    # --- Accent ---
    "accent.primary": "#F29857",
    "accent.hover": "#E88E4D",
    "accent.pressed": "#E28A48",
    "accent.subtle": "#FDEADE",
    "accent.subtleHover": "#F2E0D4",
    "accent.text": "#A35200",
    "accent.border": "#B3774E",
    "accent.focus": "#C56F2A",
    "accent.onAccent": "#1E1A17",
    # --- Semantic ---
    "semantic.success.solid": "#519D55",
    "semantic.success.subtle": "#E3F5E3",
    "semantic.success.text": "#297731",
    "semantic.success.border": "#5E9160",
    "semantic.success.onSolid": "#1E1A17",
    "semantic.warning.solid": "#EAAA40",
    "semantic.warning.subtle": "#FBEDD9",
    "semantic.warning.text": "#8D5F00",
    "semantic.warning.border": "#A67C3A",
    "semantic.warning.onSolid": "#1E1A17",
    "semantic.error.solid": "#E1524F",
    "semantic.error.subtle": "#FFE9E7",
    "semantic.error.text": "#C13335",
    "semantic.error.border": "#C5635D",
    "semantic.error.onSolid": "#1E1A17",
    "semantic.info.solid": "#3C93D5",
    "semantic.info.subtle": "#E2F1FF",
    "semantic.info.text": "#036DAC",
    "semantic.info.border": "#548AB7",
    "semantic.info.onSolid": "#1E1A17",
    # --- 数据可视化（与 Neutral / Accent / Semantic 并列的第四套） ---
    "viz.categorical.1": "#C5617F",
    "viz.categorical.2": "#78922C",
    "viz.categorical.3": "#2D8ECD",
    "viz.grid": "#DAD4D0",
    "viz.axis": "#6C6764",
}

DARK: dict[str, str] = {
    # --- Neutral：面 ---
    "canvas": "#120F0C",
    "surface": "#1A1614",
    "surfaceElevated": "#241F1D",
    "surfaceSunken": "#0B0706",
    # --- Neutral：文字 ---
    "text.primary": "#F0EAE6",
    "text.secondary": "#B5B0AC",
    "text.tertiary": "#928D89",
    "text.disabled": "#696461",
    "text.inverse": "#1E1A17",
    # --- Neutral：分隔、边界、填充 ---
    "separator.subtle": "#2D2926",
    "separator.strong": "#413D3A",
    "border.default": "#6E6966",
    "fill.control": "#201C19",
    "fill.hover": "#2D2926",
    "fill.pressed": "#3A3633",
    "scrim": "rgba(0, 0, 0, 0.60)",
    # --- Accent ---
    "accent.primary": "#FFA86A",
    "accent.hover": "#F79D5C",
    "accent.pressed": "#F29857",
    "accent.subtle": "#371F0E",
    "accent.subtleHover": "#422A19",
    "accent.text": "#FFA86A",
    "accent.border": "#965D33",
    "accent.focus": "#FFA86A",
    "accent.onAccent": "#1E1A17",
    # --- Semantic ---
    "semantic.success.solid": "#78BF7B",
    "semantic.success.subtle": "#192C19",
    "semantic.success.text": "#78BF7B",
    "semantic.success.border": "#4E7B4F",
    "semantic.success.onSolid": "#1E1A17",
    "semantic.warning.solid": "#F4B85B",
    "semantic.warning.subtle": "#32230D",
    "semantic.warning.text": "#F4B85B",
    "semantic.warning.border": "#8E682C",
    "semantic.warning.onSolid": "#1E1A17",
    "semantic.error.solid": "#F97770",
    "semantic.error.subtle": "#381E1C",
    "semantic.error.text": "#F97770",
    "semantic.error.border": "#AA5550",
    "semantic.error.onSolid": "#1E1A17",
    "semantic.info.solid": "#72B8F2",
    "semantic.info.subtle": "#14283A",
    "semantic.info.text": "#72B8F2",
    "semantic.info.border": "#477499",
    "semantic.info.onSolid": "#1E1A17",
    # --- 数据可视化 ---
    "viz.categorical.1": "#DD87A1",
    "viz.categorical.2": "#9AAF5D",
    "viz.categorical.3": "#60ADE3",
    "viz.grid": "#2D2926",
    "viz.axis": "#928D89",
}

#: 分类色的条数。图表按序取用，顺序固定，同一份数据到哪都同色同序。
VIZ_CATEGORICAL_COUNT = 3

#: 覆盖登记。规范要求项目覆盖全局默认时写出确定值与原因，不能悄悄漂移。
#: 格式：(Token 或规则, 覆盖后的确定值, 原因)
OVERRIDES: tuple[tuple[str, str, str], ...] = (
    ("Neutral Chroma", "0.008",
     "规范起点是 0.006。杏桃橙是暖色品牌，Neutral 跟着带一点暖偏，"
     "仍在 0.003–0.012 的搜索范围内，只有并排比较才看得出来。"),
    ("Light text.tertiary", "L 0.518（规范默认 0.550）",
     "默认值在 fill.control 上只有 4.3:1。text.tertiary 用于 caption（11px），"
     "按规范不算大号文本，要 4.5:1。可访问性底线高于全局默认值。"),
    ("Dark text.tertiary", "L 0.646（规范默认 0.640）",
     "默认值在 semantic.success.subtle 上差一点到 4.5:1，同上。"),
    ("accent 状态方向", "Light 与 Dark 都朝变暗走（Hover -0.03，Pressed -0.045）",
     "规范只给幅度不给方向，并要求 Pressed 与按压反馈方向一致、幅度大于 Hover。"
     "同方向递增才满足这条。深色下因此与 Fluent 原生按钮的提亮方向相反，"
     "但 QSS 化的控件按规范算自绘控件，用本文默认值而不是平台状态资源。"),
    ("Light semantic.error.solid", "L 0.630（同族其余 solid 的骨架是 0.628）",
     "0.628 时统一的 onSolid 只有 4.49:1，差 0.01 到 AA。按规范提亮 Solid，"
     "不压暗它——红色需要更强时改用 error.text 或 error.border。"),
    ("viz 色相回避集", "error 25° / success 145° / warning 76° / 品牌 55°，各至少 20°",
     "规范只要求回避三个语义色相。品牌色相一并回避，"
     "否则分类色会被读成「当前选中」而不是「某个类别」。"),
    ("Focus 环偏移", "画在控件边界外 2px，由 ui.widgets.FocusRing 统一绘制",
     "Qt 的 QSS 不支持 outline / outline-offset（已实测，属性被静默忽略），"
     "焦点环改由一个覆盖层部件画，位置和圆角跟随获得焦点的控件。"),
    ("QLabel 行高", "会换行的标签用富文本 <div style=\"line-height:…\"> 设定",
     "Qt 的 QSS 不认 line-height，但富文本引擎认（已实测生效）。"
     "单行标签的高度由字号决定，不需要这层包装。"),
)
