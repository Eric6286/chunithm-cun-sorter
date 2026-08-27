# -*- coding: utf-8 -*-
"""按 HIG 版式手搓的几个部件：拨动开关、inset grouped 卡片、统计块、曲线、浮条。

Qt 自带的 QCheckBox 只有勾选框那一种形态，而 HIG 里「开或关」要用拨动开关、
「从一堆里挑几个」才用勾选框，所以开关得自己画。
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, QRectF,
                            QSize, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget)

from . import theme


# ----------------------------- 拨动开关 -------------------------------------
class Switch(QAbstractButton):
    """iOS/macOS 那种拨动开关。用于「开或关」这一类二选一。"""

    _W, _H, _PAD = 42, 24, 2

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
    """

    def __init__(self, label: str, sublabel: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._box = QHBoxLayout(self)
        self._box.setContentsMargins(theme.GRID * 2, theme.GRID, theme.GRID * 2, theme.GRID)
        self._box.setSpacing(theme.GRID * 1.5)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        self.label = QLabel(label)
        text_col.addWidget(self.label)
        self.sublabel: QLabel | None = None
        if sublabel:
            self.sublabel = caption(sublabel)
            text_col.addWidget(self.sublabel)
        self._box.addLayout(text_col)
        self._box.addStretch(1)
        self.setMinimumHeight(theme.ROW_HEIGHT)

    def add(self, *widgets: QWidget) -> None:
        for w in widgets:
            self._box.addWidget(w)

    def set_sublabel(self, text: str) -> None:
        if self.sublabel is not None:
            self.sublabel.setText(text)


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
