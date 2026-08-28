# -*- coding: utf-8 -*-
"""配色、字号、样式表——全应用只有这一份。

照 Apple HIG 的深色模式做：语义色 + label / fill / separator 三档灰阶，
inset grouped 版式（标题在框外、内容在圆角框里、行间一条细分割线、
补充说明在框外下方），控件圆角 6、容器圆角 10、间距走 8pt 网格。

⚠️ **字号一律按像素给**（``setPixelSize`` / QSS 的 ``px``）。HIG 那张字体样式表
（正文 13、小标题 11、脚注 10、大数字 22）在 macOS 上 1pt 就是 1px，而 Qt 在
Windows 上按 96 DPI 把 pt 换成 px——13pt 会变成 17px，整屏字大一圈，行还会被
挤到标签和副标题叠在一起。写 ``pt`` 就是这个后果。

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

#: Mica 打开时的那一套底色。窗口和侧栏自己**不画**，材质才透得上来；
#: 内容区、卡片、输入框逐层压半透明，越靠上越不透。
#: 原色比不透明那套亮一档是有意的——材质本身偏暗，半透明之后每层都会往下沉，
#: 照搬不透明的取值层与层的落差就糊掉了。
BG_WINDOW_MICA = "transparent"
BG_SIDEBAR_MICA = "transparent"
BG_CONTENT_MICA = "transparent"
BG_CARD_MICA = alpha("#3A3A3C", 0.55)
BG_FIELD_MICA = alpha("#48484A", 0.60)

FILL = "rgba(120, 120, 128, 0.36)"
FILL_HOVER = "rgba(120, 120, 128, 0.48)"
SEPARATOR = "rgba(255, 255, 255, 0.10)"

# ----------------------------- 字号 -----------------------------------------
#: macOS 字体样式表，单位是**像素**：正文 13、小标题 11、脚注 10、大数字 22
FS_BODY = 13
FS_SUBHEAD = 11
FS_FOOTNOTE = 10
FS_NUMBER = 22
FS_TITLE = 15
#: 页面大标题
FS_PAGE = 22

_FONT_STACK = ("SF Pro Text", "SF Pro Display", "Segoe UI Variable Text",
               "Segoe UI", "PingFang SC", "苹方", "Microsoft YaHei UI", "微软雅黑")

# ----------------------------- 尺寸 -----------------------------------------
R_CONTROL = 6
R_CONTAINER = 10
#: 8pt 网格
GRID = 8
#: 一行的最小高度。单行行靠它撑出呼吸感，两行的行由内容自己长——
#: 别拿它当上限，见 :class:`ui.widgets.Row`
ROW_HEIGHT = 36


def ui_font(size: int = FS_BODY, bold: bool = False) -> QFont:
    """整条字体栈交给 Qt，让它**逐字符**回退。

    别写成「挑第一个装了的家族」：Segoe UI 之类的界面字体没有汉字字形，
    选中它之后中文要么走系统兜底、要么直接是豆腐块，而且行高会和西文对不齐。
    ``setFamilies`` 让 Qt 按顺序找有该字形的那一个，西文用 Segoe、汉字用雅黑，
    两边的字号和基线仍然一致。
    """
    font = QFont()
    font.setFamilies(list(_FONT_STACK))
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


def label_color(opacity: float = 1.0) -> QColor:
    """自绘控件用的文字色。

    :data:`LABEL_2` / :data:`LABEL_3` 是给 QSS 用的 ``rgba(...)`` 字符串，
    ``QColor`` 解析不了；画笔要用这个函数取色。
    """
    c = QColor(235, 235, 245)
    c.setAlphaF(opacity)
    return c


def stylesheet(mica: bool = False) -> str:
    """全应用的样式表。挂在 QApplication 上。

    ``mica=True`` 换成透得过 Mica 的那套底色。**对话框始终不透明**：
    材质是给主窗口那一层用的，小对话框跟着透只会看不清。
    """
    bg_window = BG_WINDOW_MICA if mica else BG_WINDOW
    bg_sidebar = BG_SIDEBAR_MICA if mica else BG_SIDEBAR
    bg_content = BG_CONTENT_MICA if mica else "transparent"
    bg_card = BG_CARD_MICA if mica else BG_CARD
    bg_field = BG_FIELD_MICA if mica else BG_FIELD
    return f"""
/* 只给真正的容器画底色，绝不写 QWidget 类型选择器 */
QMainWindow {{
    background: {bg_window};
}}
QDialog {{
    background: {BG_WINDOW};
}}
QWidget#Sidebar {{
    background: {bg_sidebar};
    border-right: 1px solid {SEPARATOR};
}}
QStackedWidget#ContentPane {{
    background: {bg_content};
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
    font-size: {FS_SUBHEAD}px;
}}
QLabel[role="caption"] {{
    color: {LABEL_3};
    font-size: {FS_FOOTNOTE}px;
}}
QLabel[role="value"] {{
    color: {LABEL};
    font-size: {FS_NUMBER}px;
}}
QLabel[role="title"] {{
    color: {LABEL};
    font-size: {FS_TITLE}px;
}}
QLabel[role="page"] {{
    color: {LABEL};
    font-size: {FS_PAGE}px;
    font-weight: 600;
}}
QLabel:disabled {{
    color: {LABEL_3};
}}

/* inset grouped 的圆角框 */
QFrame#Card {{
    background: {bg_card};
    border: 1px solid {alpha('#FFFFFF', 0.07)};
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
    font-size: {FS_BODY}px;
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
/* 列表里的删除：平时只是个淡叉，指上去才变红。一列五个红「删除」太吵 */
QPushButton[role="remove"] {{
    background: transparent;
    color: {LABEL_3};
    border-radius: {R_CONTROL}px;
    padding: 2px 9px;
    font-size: {FS_TITLE}px;
}}
QPushButton[role="remove"]:hover {{
    background: {alpha(RED, 0.16)};
    color: {RED};
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
    background: {bg_field};
    color: {LABEL};
    border: 1px solid transparent;
    border-radius: {R_CONTROL}px;
    padding: 4px 8px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
    font-size: {FS_BODY}px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:read-only {{
    color: {LABEL_2};
}}
/* 只读的路径不是给人填的，别画成输入框——当行里的「值」排版就够了 */
QLineEdit[role="path"] {{
    background: transparent;
    border: none;
    padding: 0;
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
    width: 20px;
}}
/* down-arrow 一律不覆盖：QSS 拿边框拼的三角在 Qt 里会画成一个实心方块，
   反而比系统箭头难看。样式化 drop-down 只是为了去掉那个凸起的按钮框。 */
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
    font-size: {FS_BODY}px;
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
    font-size: {FS_BODY}px;
}}
QListWidget#NavList::item {{
    color: {LABEL_2};
    border-radius: {R_CONTROL}px;
    padding: 0 10px;
    margin: 1px 8px;
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
