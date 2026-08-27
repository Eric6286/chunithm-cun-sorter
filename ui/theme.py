# -*- coding: utf-8 -*-
"""配色、字号、样式表——全应用只有这一份。

照 Apple HIG 的深色模式做：语义色 + label / fill / separator 三档灰阶，
inset grouped 版式（标题在框外、内容在圆角框里、行间一条细分割线、
补充说明在框外下方），控件圆角 6、容器圆角 10、间距走 8pt 网格。

**强调色只有 :data:`ACCENT` 一个常量**，hover / pressed / 半透明态全从它推导。
换主色只改那一行，不会漏。

⚠️ QSS 里**绝对不要写** ``QWidget { background: ... }``。Qt 的类型选择器连
子类一起命中，每个 QLabel 都会被刷上底色，在卡片上显示成一条条横杠。
背景只画在真正需要的容器上（用 objectName 选择器）。
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# ----------------------------- 强调色 ---------------------------------------
#: 活力橙。这个项目的主题色，见 ~/.claude/CLAUDE.md 的项目配色表。
ACCENT = "#FF6B35"
#: 橙色够亮，填充上压黑字才够对比度（白字只有 2.4:1）
ON_ACCENT = "#000000"


def mix(a: str, b: str, ratio: float) -> str:
    """把 ``a`` 往 ``b`` 混 ``ratio`` 比例，返回 ``#rrggbb``。"""
    ca, cb = QColor(a), QColor(b)
    r = round(ca.red() * (1 - ratio) + cb.red() * ratio)
    g = round(ca.green() * (1 - ratio) + cb.green() * ratio)
    bl = round(ca.blue() * (1 - ratio) + cb.blue() * ratio)
    return f"#{r:02x}{g:02x}{bl:02x}"


def alpha(color: str, a: float) -> str:
    """``rgba(...)`` 形式的半透明色，给 QSS 用。"""
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {a:.3f})"


ACCENT_HOVER = mix(ACCENT, "#FFFFFF", 0.14)
ACCENT_PRESSED = mix(ACCENT, "#000000", 0.14)
ACCENT_SOFT = alpha(ACCENT, 0.22)
ACCENT_DISABLED = alpha(ACCENT, 0.30)

# ----------------------------- 语义色 ---------------------------------------
# Apple 深色模式取值
BLUE = "#0A84FF"
GREEN = "#30D158"
ORANGE = "#FF9F0A"
#: 只表示破坏性动作，不作任何项目的主题色
RED = "#FF453A"

# ----------------------------- 灰阶 -----------------------------------------
BG_WINDOW = "#1C1C1E"
BG_SIDEBAR = "#161618"
BG_CARD = "#2C2C2E"
BG_FIELD = "#3A3A3C"

LABEL = "#FFFFFF"
LABEL_2 = "rgba(235, 235, 245, 0.60)"
LABEL_3 = "rgba(235, 235, 245, 0.30)"

FILL = "rgba(120, 120, 128, 0.36)"
FILL_HOVER = "rgba(120, 120, 128, 0.48)"
SEPARATOR = "rgba(255, 255, 255, 0.10)"

# ----------------------------- 字号 -----------------------------------------
#: macOS 字体样式表：正文 13、小标题 11、脚注 10、大数字 22
FS_BODY = 13
FS_SUBHEAD = 11
FS_FOOTNOTE = 10
FS_NUMBER = 22
FS_TITLE = 15

_FONT_STACK = ("SF Pro Text", "SF Pro Display", "Segoe UI Variable Text",
               "Segoe UI", "PingFang SC", "苹方", "Microsoft YaHei UI", "微软雅黑")

# ----------------------------- 尺寸 -----------------------------------------
R_CONTROL = 6
R_CONTAINER = 10
#: 8pt 网格
GRID = 8
ROW_HEIGHT = 38


def ui_font(size: int = FS_BODY, bold: bool = False) -> QFont:
    """整条字体栈交给 Qt，让它**逐字符**回退。

    别写成「挑第一个装了的家族」：Segoe UI 之类的界面字体没有汉字字形，
    选中它之后中文要么走系统兜底、要么直接是豆腐块，而且行高会和西文对不齐。
    ``setFamilies`` 让 Qt 按顺序找有该字形的那一个，西文用 Segoe、汉字用雅黑，
    两边的字号和基线仍然一致。
    """
    font = QFont()
    font.setFamilies(list(_FONT_STACK))
    font.setPointSize(size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


def stylesheet() -> str:
    """全应用的样式表。挂在 QApplication 上。"""
    return f"""
/* 只给真正的容器画底色，绝不写 QWidget 类型选择器 */
QMainWindow, QDialog {{
    background: {BG_WINDOW};
}}
QWidget#Sidebar {{
    background: {BG_SIDEBAR};
    border-right: 1px solid {SEPARATOR};
}}
QWidget#PageBody, QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {{
    background: transparent;
}}

QLabel {{
    color: {LABEL};
    background: transparent;
}}
QLabel[role="section"] {{
    color: {LABEL_2};
    font-size: {FS_SUBHEAD}pt;
}}
QLabel[role="caption"] {{
    color: {LABEL_3};
    font-size: {FS_FOOTNOTE}pt;
}}
QLabel[role="value"] {{
    color: {LABEL};
    font-size: {FS_NUMBER}pt;
}}
QLabel[role="title"] {{
    color: {LABEL};
    font-size: {FS_TITLE}pt;
}}
QLabel:disabled {{
    color: {LABEL_3};
}}

/* inset grouped 的圆角框 */
QFrame#Card {{
    background: {BG_CARD};
    border: none;
    border-radius: {R_CONTAINER}px;
}}
QFrame#Separator {{
    background: {SEPARATOR};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

QPushButton {{
    background: {FILL};
    color: {LABEL};
    border: none;
    border-radius: {R_CONTROL}px;
    padding: 6px 14px;
    font-size: {FS_BODY}pt;
}}
QPushButton:hover {{
    background: {FILL_HOVER};
}}
QPushButton:pressed {{
    background: {alpha('#000000', 0.25)};
}}
QPushButton:disabled {{
    color: {LABEL_3};
}}
QPushButton[role="accent"] {{
    background: {ACCENT};
    color: {ON_ACCENT};
}}
QPushButton[role="accent"]:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton[role="accent"]:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton[role="accent"]:disabled {{
    background: {ACCENT_DISABLED};
    color: {alpha(ON_ACCENT, 0.45)};
}}
/* 破坏性动作只把字变红，不做红底按钮 */
QPushButton[role="destructive"] {{
    background: transparent;
    color: {RED};
}}
QPushButton[role="destructive"]:hover {{
    background: {alpha(RED, 0.14)};
}}
QPushButton[role="quiet"] {{
    background: transparent;
    color: {LABEL_2};
    padding: 4px 8px;
}}
QPushButton[role="quiet"]:hover {{
    background: {FILL};
    color: {LABEL};
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {BG_FIELD};
    color: {LABEL};
    border: 1px solid transparent;
    border-radius: {R_CONTROL}px;
    padding: 4px 8px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
    font-size: {FS_BODY}pt;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:read-only {{
    color: {LABEL_2};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {LABEL_3};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0px;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {BG_FIELD};
    color: {LABEL};
    border: 1px solid {SEPARATOR};
    border-radius: {R_CONTROL}px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
    outline: none;
}}

QCheckBox {{
    color: {LABEL};
    spacing: 8px;
    font-size: {FS_BODY}pt;
}}
QCheckBox:disabled {{
    color: {LABEL_3};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {LABEL_3};
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

QScrollArea {{
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {alpha('#FFFFFF', 0.18)};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {alpha('#FFFFFF', 0.28)};
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
    background: {alpha('#FFFFFF', 0.18)};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: transparent;
}}

/* 左侧导航 */
QListWidget#NavList {{
    background: transparent;
    border: none;
    outline: none;
    font-size: {FS_BODY}pt;
}}
QListWidget#NavList::item {{
    color: {LABEL_2};
    border-radius: {R_CONTROL}px;
    padding: 7px 10px;
    margin: 2px 8px;
}}
QListWidget#NavList::item:hover {{
    background: {FILL};
    color: {LABEL};
}}
QListWidget#NavList::item:selected {{
    background: {ACCENT};
    color: {ON_ACCENT};
}}

QToolTip {{
    background: {BG_FIELD};
    color: {LABEL};
    border: 1px solid {SEPARATOR};
    border-radius: {R_CONTROL}px;
    padding: 4px 8px;
}}

QMenu {{
    background: {BG_CARD};
    color: {LABEL};
    border: 1px solid {SEPARATOR};
    border-radius: {R_CONTROL}px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: {ON_ACCENT};
}}
"""
