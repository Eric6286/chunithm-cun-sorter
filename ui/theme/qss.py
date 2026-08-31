# -*- coding: utf-8 -*-
"""语义 Token → QSS。全应用**唯一**拼样式表的地方。

⚠️ 绝不要写 ``QWidget { background: ... }`` 这类**无祖先限定**的类型选择器。
Qt 的类型选择器连子类一起命中，每个 QLabel 都会被刷上底色，在卡片上显示成
一条条横杠。背景只画在明确命名的容器上（objectName 选择器），或者带祖先限定的
后代选择器（``QScrollArea#PageScroll > QWidget`` 这种是安全的）。
``tests/test_theme.py`` 钉着这条。

⚠️ QSS **不支持** ``outline`` / ``outline-offset``（已实测：属性被静默忽略，
一个像素都不画）。焦点环由 :class:`ui.widgets.FocusRing` 统一绘制，所以这里
没有 ``:focus`` 的边框规则——加了反而会让控件在获得焦点时跳动一下。
"""

from __future__ import annotations

from . import metrics as m


def alpha(hex_color: str, a: float) -> str:
    """``#rrggbb`` → ``rgba(r, g, b, a)``，给 Mica 那套半透明层用。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {a:.3f})"


def build(t: dict[str, str], mica: bool) -> str:
    """按一套 Token 生成整份样式表。

    ``mica=True`` 时窗口和侧栏自己不画底色（材质是 DWM 铺在窗口**后面**的，
    窗口那层像素不透明就等于把它整个盖住），其余各层压半透明。
    **对话框始终不透明**：材质是给主窗口那一层用的，小对话框跟着透只会看不清。
    """
    window_bg = "transparent" if mica else t["canvas"]
    sidebar_bg = "transparent" if mica else t["surface"]
    card_bg = alpha(t["surface"], m.MATERIAL_SURFACE_ALPHA) if mica else t["surface"]
    elevated_bg = (alpha(t["surfaceElevated"], m.MATERIAL_ELEVATED_ALPHA)
                   if mica else t["surfaceElevated"])
    sunken_bg = alpha(t["surfaceSunken"], m.MATERIAL_SUNKEN_ALPHA) if mica else t["surfaceSunken"]
    field_bg = alpha(t["fill.control"], m.MATERIAL_FILL_ALPHA) if mica else t["fill.control"]

    return f"""
/* ===== 面 ===== 只给明确命名的容器画底色，绝不写无限定的 QWidget 选择器 */

/* ⚠️ 画布底色画在 **AppRoot** 上，不是 QMainWindow 上。
   窗口一旦设过 WA_TranslucentBackground，QMainWindow 自己的 QSS 背景就**不画了**
   （实测：同一份样式表，非透明窗口取到 #120F0C，透明窗口取到 alpha=0）。
   而那个属性只能在 show() 之前设、之后撤不掉，于是「Mica 没铺上就换回不透明」
   那条回退会失效，整个窗口一片全黑。改画在中央容器上就与窗口属性无关了。 */
QWidget#AppRoot {{
    background: {window_bg};
}}
QMainWindow {{
    background: {window_bg};
}}
QDialog {{
    background: {t["canvas"]};
}}
QWidget#Sidebar {{
    background: {sidebar_bg};
    border-right: 1px solid {t["separator.subtle"]};
}}
QStackedWidget#ContentPane {{
    background: transparent;
}}
QWidget#PageBody, QScrollArea#PageScroll,
QScrollArea#PageScroll > QWidget > QWidget {{
    background: transparent;
}}

/* Card：surface + radius.large + 无阴影。surface 与 canvas 的对比度低于
   1.1:1，按规范要补一条 separator.subtle 边界，否则卡片边缘看不出来。 */
QFrame#Card {{
    background: {card_bg};
    border: 1px solid {t["separator.subtle"]};
    border-radius: {m.RADIUS_LARGE}px;
}}
/* Sunken：内嵌的绘图区与日志区。规范要求 Sunken 带 separator.subtle 边界。 */
QFrame#Sunken {{
    background: {sunken_bg};
    border: 1px solid {t["separator.subtle"]};
    border-radius: {m.RADIUS_MEDIUM}px;
}}
/* Elevated：浮层。规范要求无边框，靠 elevation.2 表达层级。 */
QFrame#Toast {{
    background: {elevated_bg};
    border: none;
    border-radius: {m.RADIUS_LARGE}px;
}}
QFrame#Separator {{
    background: {t["separator.subtle"]};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

/* ===== 文字 ===== 角色由 role 属性选，默认是 body */
QLabel {{
    color: {t["text.primary"]};
    background: transparent;
    font-size: {m.BODY.size}px;
}}
QLabel[role="page"] {{
    color: {t["text.primary"]};
    font-size: {m.PAGE_TITLE.size}px;
    font-weight: {m.PAGE_TITLE.weight};
}}
QLabel[role="title"] {{
    color: {t["text.primary"]};
    font-size: {m.TITLE.size}px;
    font-weight: {m.TITLE.weight};
}}
/* 组标题：必须比行标题大、Semibold、text.primary。
   v2.0 是 11px 弱灰，规范点名禁止这么做。 */
QLabel[role="section"] {{
    color: {t["text.primary"]};
    font-size: {m.SECTION_TITLE.size}px;
    font-weight: {m.SECTION_TITLE.weight};
}}
QLabel[role="secondary"] {{
    color: {t["text.secondary"]};
    font-size: {m.SECONDARY.size}px;
}}
QLabel[role="caption"] {{
    color: {t["text.tertiary"]};
    font-size: {m.CAPTION.size}px;
}}
QLabel[role="metric"] {{
    color: {t["text.primary"]};
    font-size: {m.METRIC.size}px;
    font-weight: {m.METRIC.weight};
}}
QLabel:disabled {{
    color: {t["text.disabled"]};
}}

/* ===== 按钮 ===== fill.control 与 surface 只差 1.13:1，远不到 3:1，
   所以必须有 border.default 的边界，否则控件边缘无法识别。 */
QPushButton {{
    background: {field_bg};
    color: {t["text.primary"]};
    border: 1px solid {t["border.default"]};
    border-radius: {m.RADIUS_SMALL}px;
    padding: {m.PADDING_CONTROL_Y - 1}px {m.PADDING_CONTROL_X}px;
    font-size: {m.BUTTON.size}px;
    font-weight: {m.BUTTON.weight};
}}
QPushButton:hover {{
    background: {t["fill.hover"]};
}}
QPushButton:pressed {{
    background: {t["fill.pressed"]};
}}
QPushButton:disabled {{
    color: {t["text.disabled"]};
    border-color: {t["separator.subtle"]};
}}
QPushButton[role="accent"] {{
    background: {t["accent.primary"]};
    color: {t["accent.onAccent"]};
    border: 1px solid {t["accent.primary"]};
}}
QPushButton[role="accent"]:hover {{
    background: {t["accent.hover"]};
    border-color: {t["accent.hover"]};
}}
QPushButton[role="accent"]:pressed {{
    background: {t["accent.pressed"]};
    border-color: {t["accent.pressed"]};
}}
/* 停用不靠降低不透明度，换成 Disabled Token。
   规范禁止在 text.disabled 之上再叠一层 alpha。 */
QPushButton[role="accent"]:disabled {{
    background: {t["fill.control"]};
    color: {t["text.disabled"]};
    border-color: {t["separator.subtle"]};
}}
/* 破坏性动作用独立的 error 语义，而且必须有常驻文字，不能只留一个图标。 */
QPushButton[role="destructive"] {{
    background: transparent;
    color: {t["semantic.error.text"]};
    border: 1px solid {t["semantic.error.border"]};
}}
QPushButton[role="destructive"]:hover {{
    background: {t["semantic.error.subtle"]};
}}
QPushButton[role="destructive"]:pressed {{
    background: {t["semantic.error.subtle"]};
    border-color: {t["semantic.error.text"]};
}}
QPushButton[role="destructive"]:disabled {{
    color: {t["text.disabled"]};
    border-color: {t["separator.subtle"]};
}}
QPushButton[role="quiet"] {{
    background: transparent;
    color: {t["text.secondary"]};
    border: 1px solid transparent;
}}
QPushButton[role="quiet"]:hover {{
    background: {t["fill.hover"]};
    color: {t["text.primary"]};
}}
QPushButton[role="quiet"]:pressed {{
    background: {t["fill.pressed"]};
}}
QPushButton[role="quiet"]:disabled {{
    color: {t["text.disabled"]};
}}
/* 只有图标的行内按钮：命中区由固定尺寸给，内边距归零，图形自己画。 */
QPushButton[role="icon"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {m.RADIUS_SMALL}px;
    padding: 0;
}}
QPushButton[role="icon"]:hover {{
    background: {t["fill.hover"]};
}}
QPushButton[role="icon"]:pressed {{
    background: {t["fill.pressed"]};
}}
/* Segmented：2–4 个互斥、标签简短、需要直接比较。选中态用 accent.subtle
   染色而不是整块灌品牌色——品牌色是染色剂不是油漆。 */
QPushButton[role="segment"] {{
    background: {field_bg};
    color: {t["text.secondary"]};
    border: 1px solid {t["border.default"]};
    border-radius: {m.RADIUS_SMALL}px;
    padding: {m.PADDING_CONTROL_Y - 2}px {m.PADDING_CONTROL_X}px;
    font-size: {m.BUTTON.size}px;
    font-weight: {m.BUTTON.weight};
}}
QPushButton[role="segment"]:hover {{
    background: {t["fill.hover"]};
    color: {t["text.primary"]};
}}
QPushButton[role="segment"]:checked {{
    background: {t["accent.subtle"]};
    color: {t["accent.text"]};
    border-color: {t["accent.border"]};
}}
QPushButton[role="segment"]:disabled {{
    color: {t["text.disabled"]};
    border-color: {t["separator.subtle"]};
}}

/* ===== 输入 ===== 同上：fill.control + 1px border.default */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {field_bg};
    color: {t["text.primary"]};
    border: 1px solid {t["border.default"]};
    border-radius: {m.RADIUS_SMALL}px;
    padding: {m.PADDING_CONTROL_Y - 1}px {m.PADDING_CONTROL_X - 4}px;
    selection-background-color: {t["accent.primary"]};
    selection-color: {t["accent.onAccent"]};
    font-size: {m.BODY.size}px;
}}
QLineEdit[state="error"], QSpinBox[state="error"], QDoubleSpinBox[state="error"] {{
    border: 2px solid {t["semantic.error.border"]};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QPlainTextEdit:disabled {{
    color: {t["text.disabled"]};
    border-color: {t["separator.subtle"]};
}}
/* 只读的路径不是给人填的：当行里的「值」排版就够了。
   规范：行标题与右侧值共享同一 body 字号，右侧值用 text.secondary。 */
QLineEdit[role="path"] {{
    background: transparent;
    border: none;
    padding: 0;
    color: {t["text.secondary"]};
}}
QLineEdit[role="path"]:disabled {{
    color: {t["text.disabled"]};
}}
/* 日志区是 Sunken 的 Console */
QPlainTextEdit#LogBox {{
    background: {sunken_bg};
    border: 1px solid {t["separator.subtle"]};
    border-radius: {m.RADIUS_MEDIUM}px;
    padding: {m.PADDING_CONTAINER}px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0px;
}}
/* drop-down 只去掉那个凸起的按钮框；箭头由 widgets.Combo 自己描，
   因为 drop-down 一 styled，Windows 样式就不画箭头了，下拉框看上去和只读
   输入框一模一样。QSS 拿边框拼的三角在 Qt 里会画成一个实心方块。 */
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {t["surfaceElevated"]};
    color: {t["text.primary"]};
    border: 1px solid {t["separator.subtle"]};
    border-radius: {m.RADIUS_SMALL}px;
    selection-background-color: {t["accent.subtle"]};
    selection-color: {t["accent.text"]};
    outline: none;
}}

/* ===== 滚动条 ===== */
QScrollArea {{
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t["separator.strong"]};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t["border.default"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {t["separator.strong"]};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {t["border.default"]};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: transparent;
}}

/* ===== 左侧导航 ===== 选中态用 accent.subtle 染色 + 左侧指示条，
   不把整条灌满品牌色。 */
QListWidget#NavList {{
    background: transparent;
    border: none;
    outline: none;
    font-size: {m.BODY.size}px;
}}
QListWidget#NavList::item {{
    color: {t["text.secondary"]};
    border-radius: {m.RADIUS_SMALL}px;
    border-left: 3px solid transparent;
    padding: 0 {m.GAP_INLINE}px;
    margin: 1px {m.GAP_INLINE}px;
}}
QListWidget#NavList::item:hover {{
    background: {t["fill.hover"]};
    color: {t["text.primary"]};
}}
QListWidget#NavList::item:selected {{
    background: {t["accent.subtle"]};
    color: {t["accent.text"]};
    border-left: 3px solid {t["accent.primary"]};
}}

/* ===== 浮层 ===== */
QToolTip {{
    background: {t["surfaceElevated"]};
    color: {t["text.secondary"]};
    border: 1px solid {t["separator.subtle"]};
    border-radius: {m.RADIUS_SMALL}px;
    padding: {m.SPACE_1}px {m.SPACE_2}px;
    font-size: {m.SECONDARY.size}px;
}}
QMenu {{
    background: {t["surfaceElevated"]};
    color: {t["text.primary"]};
    border: 1px solid {t["separator.subtle"]};
    border-radius: {m.RADIUS_MEDIUM}px;
    padding: {m.SPACE_1}px;
}}
QMenu::item {{
    padding: {m.SPACE_2}px {m.SPACE_5}px;
    border-radius: {m.RADIUS_SMALL}px;
    font-size: {m.BODY.size}px;
}}
QMenu::item:selected {{
    background: {t["accent.subtle"]};
    color: {t["accent.text"]};
}}
QMenu::separator {{
    height: 1px;
    background: {t["separator.subtle"]};
    margin: {m.SPACE_1}px {m.SPACE_2}px;
}}
"""
