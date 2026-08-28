# -*- coding: utf-8 -*-
"""按 HIG 版式手搓的几个部件：拨动开关、inset grouped 卡片、统计块、曲线、浮条。

Qt 自带的 QCheckBox 只有勾选框那一种形态，而 HIG 里「开或关」要用拨动开关、
「从一堆里挑几个」才用勾选框，所以开关得自己画。
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (Property, QEasingCurve, QEvent, QPropertyAnimation,
                            QRectF, QSize, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QComboBox, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from . import theme


# ----------------------------- 拨动开关 -------------------------------------
class Switch(QAbstractButton):
    """iOS/macOS 那种拨动开关。用于「开或关」这一类二选一。"""

    _W, _H, _PAD = 38, 22, 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._W, self._H)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:            # noqa: N802 - Qt 的命名
        return QSize(self._W, self._H)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, v: float) -> None:
        self._offset = v
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:     # noqa: N802
        super().setChecked(checked)
        self._offset = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, _event) -> None:            # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled = self.isEnabled()

        off = QColor(120, 120, 128, 92)
        on = QColor(theme.ACCENT)
        track = QColor(
            round(off.red() + (on.red() - off.red()) * self._offset),
            round(off.green() + (on.green() - off.green()) * self._offset),
            round(off.blue() + (on.blue() - off.blue()) * self._offset),
            round(off.alpha() + (255 - off.alpha()) * self._offset),
        )
        if not enabled:
            track.setAlpha(round(track.alpha() * 0.4))

        r = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(r), r.height() / 2, r.height() / 2)

        d = self._H - self._PAD * 2
        x = self._PAD + (self._W - self._PAD * 2 - d) * self._offset
        knob = QColor(255, 255, 255, 255 if enabled else 140)
        p.setBrush(knob)
        p.drawEllipse(QRectF(x, self._PAD, d, d))
        p.end()


# ----------------------------- 页面骨架 -------------------------------------
#: 内容列的宽度上限。窗口能拉到 2000 宽，而「标签在最左、控件在最右」的行
#: 一旦拉开，中间就是一大片空白，眼睛要横扫整行才对得上——所以内容封顶居中，
#: 多出来的宽度留白。macOS 的「系统设置」和 WinUI 的设置页都是这么做的。
COLUMN_WIDTH = 840


def page_shell(owner: QWidget) -> QVBoxLayout:
    """给一页搭好「滚动 + 居中定宽列」的壳，返回往里放东西的那个布局。

    **每一页都要套滚动**：不套的话窗口一矮，布局会转而去压每张卡片，
    压到比内容还矮就糊成一团。
    """
    shell = QVBoxLayout(owner)
    shell.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setObjectName("PageScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    shell.addWidget(scroll)

    canvas = QWidget()
    canvas.setObjectName("PageBody")
    scroll.setWidget(canvas)

    centering = QHBoxLayout(canvas)
    centering.setContentsMargins(0, 0, 0, 0)
    centering.addStretch(1)

    column = QWidget()
    column.setObjectName("PageBody")
    column.setMaximumWidth(COLUMN_WIDTH)
    centering.addWidget(column, 10)
    centering.addStretch(1)

    body = QVBoxLayout(column)
    body.setContentsMargins(theme.GRID * 3, theme.GRID * 3,
                            theme.GRID * 3, theme.GRID * 4)
    body.setSpacing(theme.GRID)
    return body


def page_title(text: str) -> QLabel:
    """页面大标题。三页都要有，缺一页就显得那页没做完。"""
    lb = QLabel(text)
    lb.setProperty("role", "page")
    return lb


# ----------------------------- 下拉框 ---------------------------------------
class Combo(QComboBox):
    """下拉框。**箭头是自己画的。**

    样式表把 ``QComboBox::drop-down`` 的按钮框去掉之后，Windows 样式就不再画那个
    箭头了，下拉框看上去和只读输入框一模一样，根本看不出能点。QSS 里拿边框拼三角
    的老办法在 Qt 里会画成一个实心方块，比没有还难看，所以只能自己描一笔。

    应用内的下拉框一律用这个类，别直接用 ``QComboBox``。
    """

    #: 箭头的宽、高，以及离右边界多远
    _W, _H, _RIGHT = 9, 5, 12

    def paintEvent(self, event) -> None:             # noqa: N802 - Qt 的命名
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(theme.label_color(0.60 if self.isEnabled() else 0.30), 1.6,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx = self.width() - self._RIGHT - self._W / 2
        cy = self.height() / 2
        path = QPainterPath()
        path.moveTo(cx - self._W / 2, cy - self._H / 2)
        path.lineTo(cx, cy + self._H / 2)
        path.lineTo(cx + self._W / 2, cy - self._H / 2)
        p.drawPath(path)
        p.end()


# ----------------------------- 文本 -----------------------------------------
def section_title(text: str) -> QLabel:
    """分组标题，放在卡片**外面**上方。"""
    lb = QLabel(text)
    lb.setProperty("role", "section")
    return lb


def caption(text: str) -> QLabel:
    """补充说明，放在卡片**外面**下方，会自动换行。"""
    lb = QLabel(text)
    lb.setProperty("role", "caption")
    lb.setWordWrap(True)
    return lb


class ElidedLabel(QLabel):
    """单行副标题：装不下就从中间省略。

    卡片里的副标题**不能换行**。会换行的标签高度取决于宽度，窗口一窄就悄悄
    长成两三行，把整行顶高、连带把同一张卡片里别的行挤扁。路径这种长文本
    从中间省略最好认——头上的盘符和尾巴上的文件名都留着。
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "caption")
        self._full = text
        # 宽度 Ignored：副标题再长也不该把行撑宽，缩就是了
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._relayout()

    def setText(self, text: str) -> None:            # noqa: N802 - Qt 的命名
        self._full = text
        self._relayout()

    def text(self) -> str:
        return self._full

    def resizeEvent(self, event) -> None:            # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    def changeEvent(self, event) -> None:            # noqa: N802
        # 样式表把字号改小是在构造之后才生效的，字体一换就得重新量一次
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._relayout()

    def _relayout(self) -> None:
        width = max(self.width(), 32)
        shown = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideMiddle, width)
        super().setText(shown)
        # 只有真省略了才挂 tooltip，短文本上冒一个同样的浮层是噪音
        self.setToolTip(self._full if shown != self._full else "")


def body(text: str = "") -> QLabel:
    return QLabel(text)


def title(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setProperty("role", "title")
    return lb


# ----------------------------- 卡片与行 -------------------------------------
class Card(QFrame):
    """inset grouped 的圆角容器：行与行之间自动加一条细分割线。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(0)
        self._rows = 0

    def add_row(self, widget: QWidget) -> QWidget:
        if self._rows:
            self._box.addWidget(_separator())
        widget.setParent(self)
        self._box.addWidget(widget)
        self._rows += 1
        return widget

    def add_widget(self, widget: QWidget) -> QWidget:
        """插一个不带分割线的自定义块（比如一整段可拖动的列表）。"""
        widget.setParent(self)
        self._box.addWidget(widget)
        self._rows += 1
        return widget

    def clear(self) -> None:
        while self._box.count():
            item = self._box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._rows = 0


def _separator() -> QFrame:
    line = QFrame()
    line.setObjectName("Separator")
    line.setFrameShape(QFrame.Shape.NoFrame)
    line.setFixedHeight(1)
    return line


class Row(QWidget):
    """卡片里的一行：左边标签（可带副标题），右边控件。

    停用时**整行一起变淡**——标签也淡，不能只灰控件、文字仍然雪白。
    Qt 会把 disabled 往子部件传，样式表里 ``QLabel:disabled`` 接住。

    ⚠️ 高度**不要用** ``setMinimumHeight``。Qt 的 ``qSmartMinSize`` 里显式设过的
    最小高度会**顶掉**布局算出来的那个，于是页面一挤，行就被压到比内容还矮，
    标签和副标题直接叠在一起（v2.0 的「运行」页就是这么糊的）。地板改成加在
    标签上，行本身用 Fixed 的纵向策略，谁也压不动。
    """

    def __init__(self, label: str, sublabel: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._box = QHBoxLayout(self)
        self._box.setContentsMargins(theme.GRID * 2, theme.GRID, theme.GRID * 2, theme.GRID)
        self._box.setSpacing(theme.GRID * 2)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        self.label = QLabel(label)
        text_col.addWidget(self.label)
        # 副标题一律先建好再按需显示。建在构造函数里、只在有文案时才建，
        # 会让之后的 set_sublabel 悄悄没反应（v2.0 的「接入 start.bat」那行
        # 就是这么一直空着的）。
        self.sublabel = ElidedLabel(sublabel)
        text_col.addWidget(self.sublabel)
        self._box.addLayout(text_col, 1)
        self._apply_sublabel(sublabel)

    def add(self, *widgets: QWidget) -> None:
        for w in widgets:
            self._box.addWidget(w)

    def set_sublabel(self, text: str) -> None:
        self.sublabel.setText(text)
        self._apply_sublabel(text)

    def _apply_sublabel(self, text: str) -> None:
        """副标题空着就整条藏掉，行高的地板改由标签自己扛。"""
        self.sublabel.setVisible(bool(text))
        self.label.setMinimumHeight(0 if text else theme.ROW_HEIGHT - theme.GRID * 2)


# ----------------------------- 统计块 ---------------------------------------
class StatTile(QFrame):
    """一个大数字加一行说明。"""

    def __init__(self, caption_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        box = QVBoxLayout(self)
        box.setContentsMargins(theme.GRID * 2, theme.GRID * 1.5, theme.GRID * 2, theme.GRID * 1.5)
        box.setSpacing(2)
        self.value = QLabel("0")
        self.value.setProperty("role", "value")
        self.caption = caption(caption_text)
        box.addWidget(self.value)
        box.addWidget(self.caption)

    def set_value(self, value: int | str) -> None:
        self.value.setText(str(value))

    def set_caption(self, text: str) -> None:
        self.caption.setText(text)


# ----------------------------- 曲线 -----------------------------------------
class DailyChart(QWidget):
    """每日 寸 / AJ / FC 三条折线。数据来自 ``classifier.daily_counts``。"""

    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 46, 18, 30, 40

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: list[tuple[str, int, int, int]] = []
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data: Sequence[tuple[str, int, int, int]]) -> None:
        self._data = list(data)
        self.update()

    def paintEvent(self, _event) -> None:             # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if not self._data:
            p.setPen(QColor(235, 235, 245, 77))
            p.setFont(theme.ui_font(theme.FS_BODY))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return

        plot_w = max(1, w - self._PAD_L - self._PAD_R)
        plot_h = max(1, h - self._PAD_T - self._PAD_B)
        y_max = max(1, max(max(d[1], d[2], d[3]) for d in self._data))
        y_top = y_max + 1

        def xpos(i: int) -> float:
            if len(self._data) == 1:
                return self._PAD_L + plot_w / 2
            return self._PAD_L + plot_w * i / (len(self._data) - 1)

        def ypos(v: float) -> float:
            return self._PAD_T + plot_h * (1 - v / y_top)

        # 网格与纵轴刻度
        p.setFont(theme.ui_font(theme.FS_FOOTNOTE))
        steps = min(5, y_top)
        for s in range(steps + 1):
            v = y_top * s / steps
            y = ypos(v)
            p.setPen(QPen(QColor(255, 255, 255, 26), 1))
            p.drawLine(int(self._PAD_L), int(y), int(w - self._PAD_R), int(y))
            p.setPen(QColor(235, 235, 245, 120))
            p.drawText(0, int(y) - 8, self._PAD_L - 8, 16,
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       str(round(v)))

        for color, idx, name in ((theme.ACCENT, 1, "寸"), (theme.ORANGE, 2, "AJ"),
                                 (theme.GREEN, 3, "FC")):
            self._draw_series(p, color, idx, xpos, ypos)
            del name

        # 横轴：首、中、末三个日期，密了也不会糊成一片
        p.setPen(QColor(235, 235, 245, 120))
        marks = {0, len(self._data) // 2, len(self._data) - 1}
        for i in sorted(marks):
            label = self._data[i][0][5:]
            p.drawText(int(xpos(i)) - 28, h - self._PAD_B + 6, 56, 18,
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), label)

        # 图例
        x = self._PAD_L
        for color, label in ((theme.ACCENT, "寸"), (theme.ORANGE, "AJ"), (theme.GREEN, "FC")):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(x, 10, 8, 8))
            p.setPen(QColor(235, 235, 245, 160))
            p.drawText(int(x) + 13, 10, 40, 12,
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), label)
            x += 56
        p.end()

    def _draw_series(self, p: QPainter, color: str, idx: int, xpos, ypos) -> None:
        path = QPainterPath()
        for i, row in enumerate(self._data):
            x, y = xpos(i), ypos(row[idx])
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(color), 2))
        p.drawPath(path)

        if len(self._data) <= 60:              # 点太多就只留线，不然是一条毛毛虫
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            for i, row in enumerate(self._data):
                p.drawEllipse(QRectF(xpos(i) - 2.5, ypos(row[idx]) - 2.5, 5, 5))


# ----------------------------- 浮动提示 -------------------------------------
class Toast(QFrame):
    """盖在内容上方的一条提示，几秒后自己消失。

    悬浮而不占布局位置，出现和消失都不会让页面重排。
    """

    INFO, SUCCESS, WARNING, ERROR = "info", "success", "warning", "error"

    _ACCENTS = {INFO: theme.BLUE, SUCCESS: theme.GREEN,
                WARNING: theme.ORANGE, ERROR: theme.RED}

    closed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setVisible(False)
        box = QHBoxLayout(self)
        box.setContentsMargins(theme.GRID * 2, theme.GRID * 1.25,
                               theme.GRID * 2, theme.GRID * 1.25)
        box.setSpacing(theme.GRID * 1.5)

        self._bar = QFrame(self)
        self._bar.setFixedWidth(3)
        self._bar.setFrameShape(QFrame.Shape.NoFrame)
        box.addWidget(self._bar)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        self._title = QLabel("")
        self._message = caption("")
        text_col.addWidget(self._title)
        text_col.addWidget(self._message)
        box.addLayout(text_col, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_toast)

    def show_toast(self, title_text: str, message: str,
                   severity: str = INFO, duration_ms: int = 3000) -> None:
        self._title.setText(title_text)
        self._message.setText(message)
        color = self._ACCENTS.get(severity, theme.BLUE)
        self._bar.setStyleSheet(f"background: {color}; border-radius: 1px;")
        self.adjustSize()
        self._reposition()
        self.setVisible(True)
        self.raise_()
        self._timer.start(duration_ms)

    def hide_toast(self) -> None:
        self._timer.stop()
        self.setVisible(False)
        self.closed.emit()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = theme.GRID * 3
        width = min(max(self.sizeHint().width(), 320), max(320, parent.width() - margin * 2))
        self.setFixedWidth(width)
        self.adjustSize()
        self.move((parent.width() - self.width()) // 2, theme.GRID * 1.5)

    def parent_resized(self) -> None:
        if self.isVisible():
            self._reposition()
