# -*- coding: utf-8 -*-
"""字号、间距、圆角、动效、阴影。**纯数据，不 import PySide6。**

每一项都是解析后的**单值**，不留区间。规范的「实现前解析门槛」要求主题文件里
不出现数值区间、``auto``、``TBD``、「按需」「适量」这类占位。

⚠️ **字号一律按像素给**（``setPixelSize`` / QSS 的 ``px``）。这里的数字是**逻辑**
像素：Qt 6 的高 DPI 缩放会把它们按显示缩放放大，所以 13 在 150% 屏上渲染成
19.5 物理像素，符合规范「所有尺寸均为默认系统缩放下的逻辑尺寸」。
写 ``pt`` 会让 Qt 在 Windows 上按 96 DPI 换算，13 变成 17，整屏字大一圈、
行被挤到标签和副标题叠在一起（v2.0 就是这样）。

Windows 的辅助功能「放大文本」是**另一个**设置，Qt 不会自动应用。
:func:`ui.theme.font` 读一次系统的 TextScaleFactor 自己乘上去——规范要求
「系统字体缩放只能由框架应用一次」，Qt 没应用，所以由我们应用，只此一处。
"""

from __future__ import annotations

from typing import NamedTuple


class FontSpec(NamedTuple):
    """一个排版角色。``weight`` 用 CSS 数值，映射到 Qt 在门面里做。"""

    size: int
    line_height: int
    weight: int


REGULAR, MEDIUM, SEMIBOLD = 400, 500, 600

# ----------------------------- 排版 -----------------------------------------
#: 九个语义角色，Desktop 映射。先选角色，再由这里给字号，不用字号大小替代层级设计。
PAGE_TITLE = FontSpec(22, 28, SEMIBOLD)
TITLE = FontSpec(17, 22, SEMIBOLD)
#: ⚠️ 必须大于 ``BODY`` 且用 Semibold + ``text.primary``。
#: 规范点名禁止把组标题做成 caption、secondary 或弱灰文字——v2.0 正是 11px 弱灰。
SECTION_TITLE = FontSpec(14, 18, SEMIBOLD)
BODY = FontSpec(13, 18, REGULAR)
SECONDARY = FontSpec(12, 16, REGULAR)
CAPTION = FontSpec(11, 15, REGULAR)
METRIC = FontSpec(28, 34, SEMIBOLD)
BUTTON = FontSpec(13, 18, MEDIUM)
MONO = FontSpec(12, 18, REGULAR)

#: 全部角色，给「Token 都解析为单值」那条测试用。
FONT_ROLES: dict[str, FontSpec] = {
    "pageTitle": PAGE_TITLE, "title": TITLE, "sectionTitle": SECTION_TITLE,
    "body": BODY, "secondary": SECONDARY, "caption": CAPTION,
    "metric": METRIC, "button": BUTTON, "mono": MONO,
}

#: 只有这两个角色达到 WCAG 的「大号文本」，可以按 3:1 验收。
#: 判定条件是字号 ≥24 任意字重，或 ≥18.66 且字重达到 Bold(700)；Semibold 不放宽。
#: Mobile 的 ``pageTitle`` 也满足，但本项目是纯桌面程序，用不到。
LARGE_TEXT_ROLES = ("metric",)

# ----------------------------- 间距 -----------------------------------------
SPACE_1, SPACE_2, SPACE_3, SPACE_4 = 4, 8, 12, 16
SPACE_5, SPACE_6, SPACE_8, SPACE_10 = 20, 24, 32, 40

#: 语义间距（Desktop）。组件用这些，不在页面里临时发明相邻数值。
GAP_INLINE = 8          # 图标与标签、同一行紧密元素
GAP_RELATED = 4         # 标题与说明、值与单位
GAP_CONTROL = 8         # 同组相邻控件
GAP_GROUP = 16          # 同一 Section 内的小组
GAP_SECTION = 24        # 两个 Section

PADDING_CONTROL_X = 12
PADDING_CONTROL_Y = 8
PADDING_CONTAINER = 16
PADDING_PAGE_X = 24
PADDING_PAGE_Y = 24

# ----------------------------- Settings 版式 --------------------------------
#: 规范的 Settings 默认结构（Desktop 列）。
PAGE_TITLE_TO_SECTION = 24      # 页面标题 → 首个组标题
SECTION_TITLE_TO_CARD = 8       # 组标题 → Card
CARD_TO_NOTE = 8                # Card → 组级说明

#: 单行设置项的最小行高；含一行说明时用后者。
#: ⚠️ 地板要加在行**内部的标签**上，不能用 ``setMinimumHeight`` 给行本身定高——
#: Qt 的 ``qSmartMinSize`` 里显式设过的最小高度会顶掉布局算出来的那个，
#: 空间一紧这一行就被压到比内容还矮，标签和副标题叠在一起。
ROW_MIN_HEIGHT = 32
ROW_WITH_SUBLABEL_MIN_HEIGHT = 48

# ----------------------------- 圆角 -----------------------------------------
RADIUS_SMALL = 6        # 小控件、输入框
RADIUS_MEDIUM = 10      # 普通容器、面板
RADIUS_LARGE = 14       # Card、Sheet、大型浮层
# radius.full 是 height / 2，由控件自己算（Switch 的胶囊轨道）

# ----------------------------- Focus ----------------------------------------
#: 2px 焦点环，向外偏移 2px，中间露出控件所在的 Surface。
FOCUS_RING_WIDTH = 2
FOCUS_RING_OFFSET = 2
#: 彩色或深色 Surface 上要用双色环：外圈 accent.focus，内圈 1px 当前页面的
#: canvas / surfaceElevated，由内圈保证与控件本体分离。
FOCUS_RING_INNER_WIDTH = 1

# ----------------------------- 动效 -----------------------------------------
MOTION_IMMEDIATE = 120  # Hover、Pressed、颜色反馈
MOTION_SMALL = 180      # Toggle、Indicator、局部展开
MOTION_MEDIUM = 260     # Sheet、Popover、页面内层级切换
MOTION_LARGE = 360      # 重要空间转换

#: 进入与状态变化的缓动控制点；离场用 EASE_EXIT。
EASE_STANDARD = ((0.2, 0.0), (0.0, 1.0))
EASE_EXIT = ((0.4, 0.0), (1.0, 1.0))

#: 系统开「减少动态效果」时：位移与缩放时长设 0，颜色与透明度统一 100ms。
MOTION_REDUCED_MOVE = 0
MOTION_REDUCED_FADE = 100

# ----------------------------- 阴影 -----------------------------------------
class Shadow(NamedTuple):
    """结构化阴影定义，长度单位是逻辑像素。

    Qt 用 ``QGraphicsDropShadowEffect``：``blurRadius = blur``、
    ``offset = (x, y)``；Qt 没有 spread 概念，保持 0。
    """

    x: int
    y: int
    blur: int
    spread: int
    light: str
    dark: str


ELEVATION_1 = Shadow(0, 1, 3, 0, "rgba(0, 0, 0, 0.10)", "rgba(0, 0, 0, 0.28)")
ELEVATION_2 = Shadow(0, 4, 16, 0, "rgba(0, 0, 0, 0.14)", "rgba(0, 0, 0, 0.32)")

# ----------------------------- 材质 -----------------------------------------
#: Mica 铺上之后各层的不透明度。材质是 DWM 铺在窗口**后面**的，窗口那层像素
#: 不透明就等于把它整个盖住，所以窗口和侧栏自己不画底色，其余各层压半透明。
#: 材质没铺上时这套整个不用，回退到不透明的语义实色。
MATERIAL_SURFACE_ALPHA = 0.62
MATERIAL_ELEVATED_ALPHA = 0.86
MATERIAL_FILL_ALPHA = 0.55
MATERIAL_SUNKEN_ALPHA = 0.50

# ----------------------------- 层叠顺序 -------------------------------------
#: 浮层不靠临时数值互相压。Qt 里主要用于 ``raise_()`` 的先后和自绘覆盖层。
LAYER_CONTENT = 0
LAYER_NAV = 100
LAYER_POPOVER = 200
LAYER_SHEET = 300
LAYER_DIALOG = 400
LAYER_TOAST = 500
LAYER_TOOLTIP = 600

# ----------------------------- 图标 -----------------------------------------
ICON_INLINE = 16        # 行内
ICON_ACTION = 20        # 独立操作

# ----------------------------- 其他 -----------------------------------------
#: 内容列宽上限。窗口能拉到 2000 宽，而「标签在最左、控件在最右」的行一旦拉开，
#: 中间就是一大片空白，眼睛要横扫整行才对得上。多出来的宽度留白。
COLUMN_WIDTH = 840

#: Tooltip 最大宽度。再宽说明它不该是 Tooltip。
TOOLTIP_MAX_WIDTH = 280
#: 指针悬停后延迟显示 / 移开后消失。
TOOLTIP_DELAY_MS = 500
TOOLTIP_HIDE_MS = 100
