# -*- coding: utf-8 -*-
"""按语义 Token 手搓的几个部件：焦点环、拨动开关、分段控件、卡片、统计块、曲线、浮条。

自绘控件必须补齐 Focus、Disabled、键盘操作、DPI 缩放和辅助功能——规范对 Qt
是这么要求的，本文件里每个自绘件都照做。

⚠️ 颜色、字号、间距、圆角、动效时长**一律从 theme 取**，这里不写死任何视觉常量。
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (Property, QEvent, QPropertyAnimation, QRectF, QSize,
                            Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication,
                               QButtonGroup, QComboBox, QFrame, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme


# ----------------------------- 焦点环 ---------------------------------------
class FocusRing(QWidget):
    """跟着键盘焦点走的焦点环。一个窗口装一个，覆盖窗口里所有控件。

    规范要求焦点环画在**控件边界外** 2px、中间露出控件所在的 Surface。
    Qt 的 QSS 不支持 ``outline`` / ``outline-offset``（实测：属性被静默忽略，
    一个像素都不画），所以只能自己画一层。

    做成「跟随焦点的覆盖层」而不是给每个控件加边框，有两个好处：一是控件在获得
    焦点时不会因为边框变化而跳动；二是所有控件——包括原生的 QPushButton、
    QLineEdit 和自绘的 Switch——共用同一套焦点表现，不会各画各的。

    环是**获得焦点那个控件的兄弟**，所以被同样的祖先裁剪，滚出可视区时跟着消失，
    不会飘在滚动区外面。

    只在键盘焦点时显示（Tab / 方向键 / 快捷键），鼠标点击不显示——这是 Windows
    的惯例，也就是 Web 的 ``:focus-visible``。
    """

    #: 这些原因算键盘焦点
    _KEYBOARD = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                 Qt.FocusReason.ShortcutFocusReason, Qt.FocusReason.OtherFocusReason)

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._target: QWidget | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hide()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    # -- 跟踪焦点 --
    def eventFilter(self, obj, event) -> bool:        # noqa: N802 - Qt 的命名
        kind = event.type()
        if kind == QEvent.Type.FocusIn and isinstance(obj, QWidget):
            if event.reason() in self._KEYBOARD and self._owns(obj):
                self._attach(obj)
            else:
                self._detach()
        elif kind == QEvent.Type.FocusOut and obj is self._target:
            self._detach()
        elif obj is self._target and kind in (QEvent.Type.Resize,
                                              QEvent.Type.Move, QEvent.Type.Hide):
            if kind == QEvent.Type.Hide:
                self._detach()
            else:
                self._reposition()
        return False

    def _owns(self, widget: QWidget) -> bool:
        """只管自己这个窗口里的控件；列表类控件自己有当前项高亮，不叠环。"""
        if isinstance(widget, QAbstractItemView):
            return False
        return widget.window() is self._window and widget.parentWidget() is not None

    def _attach(self, widget: QWidget) -> None:
        if self._target is widget:
            return
        self._detach()
        self._target = widget
        widget.installEventFilter(self)
        self.setParent(widget.parentWidget())
        self._reposition()
        self.show()
        self.raise_()

    def _detach(self) -> None:
        if self._target is not None:
            self._target.removeEventFilter(self)
            self._target = None
        self.hide()

    def _reposition(self) -> None:
        w = self._target
        if w is None:
            return
        pad = theme.FOCUS_RING_OFFSET + theme.FOCUS_RING_WIDTH
        self.setGeometry(w.geometry().adjusted(-pad, -pad, pad, pad))

    # -- 绘制 --
    def paintEvent(self, _event) -> None:             # noqa: N802
        w = self._target
        if w is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pad = theme.FOCUS_RING_OFFSET + theme.FOCUS_RING_WIDTH
        half = theme.FOCUS_RING_WIDTH / 2.0
        rect = QRectF(self.rect()).adjusted(half, half, -half, -half)

        radius = w.property("focusRadius")
        base = theme.RADIUS_SMALL if radius is None else float(radius)
        r = base + pad - half

        # 彩色或深色 Surface 上要用双色环：外圈 accent.focus，内圈 1px 当前页面的
        # 底色，由内圈保证焦点环和控件本体分得开。
        if w.property("role") in ("accent",):
            inner = QRectF(self.rect()).adjusted(pad - 0.5, pad - 0.5,
                                                 -(pad - 0.5), -(pad - 0.5))
            p.setPen(QPen(theme.qcolor("surfaceElevated"),
                          theme.FOCUS_RING_INNER_WIDTH))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(inner, base + 0.5, base + 0.5)

        p.setPen(QPen(theme.qcolor("accent.focus"), theme.FOCUS_RING_WIDTH))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, r, r)
        p.end()


# ----------------------------- 拨动开关 -------------------------------------
class Switch(QAbstractButton):
    """「开或关」用的拨动开关。

    轨道和旋钮都描一圈边：``fill.control`` 与 ``surface`` 只差 1.13:1，
    ``accent.primary`` 与 ``surface`` 也只有约 2:1，都到不了状态图形要求的 3:1，
    所以边界必须由 ``border.default`` / ``accent.border`` 承担。

    停用时换 Disabled Token，**不是**在原色上再压一层透明度——规范禁止那么做。
    """

    _W, _H, _PAD = 40, 24, 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(self._W, self._H)
        self.setProperty("focusRadius", self._H / 2.0)      # radius.full
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(theme.duration(theme.MOTION_SMALL))
        self._anim.setEasingCurve(theme.easing())
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:                     # noqa: N802 - Qt 的命名
        return QSize(self._W, self._H)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, v: float) -> None:
        self._offset = v
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setDuration(theme.duration(theme.MOTION_SMALL))
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
        k = self._offset

        if not enabled:
            track, edge, knob = (theme.qcolor("fill.control"),
                                 theme.qcolor("separator.subtle"),
                                 theme.qcolor("text.disabled"))
        else:
            track = _blend(theme.qcolor("fill.control"), theme.qcolor("accent.primary"), k)
            edge = _blend(theme.qcolor("border.default"), theme.qcolor("accent.border"), k)
            knob = _blend(theme.qcolor("text.secondary"), theme.qcolor("accent.onAccent"), k)

        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(edge, 1))
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        d = self._H - self._PAD * 2 - 2
        x = self._PAD + 1 + (self._W - self._PAD * 2 - 2 - d) * k
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(knob)
        p.drawEllipse(QRectF(x, self._PAD + 1, d, d))
        p.end()


def _blend(a: QColor, b: QColor, k: float) -> QColor:
    return QColor(round(a.red() + (b.red() - a.red()) * k),
                  round(a.green() + (b.green() - a.green()) * k),
                  round(a.blue() + (b.blue() - a.blue()) * k))


# ----------------------------- 分段控件 -------------------------------------
class Segmented(QWidget):
    """2–4 个互斥、标签简短、需要直接比较时用这个，不用下拉框。

    用一组 checkable 的 QPushButton 拼，而不是自绘：原生按钮自带
    Hover / Pressed / Checked / Disabled 和键盘操作，焦点环也走统一那一套。
    """

    changed = Signal(int)

    def __init__(self, labels: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(theme.SPACE_1)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setProperty("role", "segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(b, i)
            box.addWidget(b)
        self._group.idClicked.connect(self.changed.emit)

    def set_current(self, index: int) -> None:
        button = self._group.button(index)
        if button is not None:
            button.setChecked(True)

    def current(self) -> int:
        return self._group.checkedId()


# ----------------------------- 页面骨架 -------------------------------------
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
    column.setMaximumWidth(theme.COLUMN_WIDTH)
    centering.addWidget(column, 10)
    centering.addStretch(1)

    body = QVBoxLayout(column)
    body.setContentsMargins(theme.PADDING_PAGE_X, theme.PADDING_PAGE_Y,
                            theme.PADDING_PAGE_X, theme.PADDING_PAGE_Y)
    body.setSpacing(0)
    return body


# ----------------------------- 下拉框 ---------------------------------------
class Combo(QComboBox):
    """下拉框。**箭头是自己画的。**

    样式表把 ``QComboBox::drop-down`` 的按钮框去掉之后，Windows 样式就不再画那个
    箭头了，下拉框看上去和只读输入框一模一样，根本看不出能点。QSS 里拿边框拼三角
    的老办法在 Qt 里会画成一个实心方块，比没有还难看，所以只能自己描一笔。

    应用内的下拉框一律用这个类，别直接用 ``QComboBox``。
    """

    _W, _H, _RIGHT = 9, 5, 12

    def paintEvent(self, event) -> None:             # noqa: N802 - Qt 的命名
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = theme.qcolor("text.secondary" if self.isEnabled() else "text.disabled")
        p.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx = self.width() - self._RIGHT - self._W / 2
        cy = self.height() / 2
        path = QPainterPath()
        path.moveTo(cx - self._W / 2, cy - self._H / 2)
        path.lineTo(cx, cy + self._H / 2)
        path.lineTo(cx + self._W / 2, cy - self._H / 2)
        p.drawPath(path)
        p.end()


# ----------------------------- 图标按钮 -------------------------------------
class IconButton(QPushButton):
    """只有图标的行内按钮。目前就一个箭头，用来给整理维度换顺序。

    重排序是高频、无破坏性、含义明确的动作，规范允许只用图标。但**触屏拿不到
    hover、屏幕阅读器拿不到图形**，所以 Tooltip 和 accessibleName 一个都不能省。

    箭头自己描，和 :class:`Combo` 的下拉箭头同一套笔画（同样的宽高比、线宽和
    圆角端点），免得应用里出现两种风格的三角。项目没有图标家族，与其混搭一个
    字符当图标，不如把仅有的这一种画一致。
    """

    UP, DOWN = "up", "down"

    #: 箭头的宽高。规范给桌面行内图标的默认尺寸是 16，这是那 16 里的墨迹部分。
    _W, _H = 9, 5
    _SIZE = 28                                   # 命中区，比图形大

    def __init__(self, direction: str, tooltip: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._direction = direction
        self.setProperty("role", "icon")
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)

    def paintEvent(self, event) -> None:             # noqa: N802 - Qt 的命名
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = theme.qcolor("text.secondary" if self.isEnabled() else "text.disabled")
        p.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        tip = self._H / 2 if self._direction == self.DOWN else -self._H / 2
        path = QPainterPath()
        path.moveTo(cx - self._W / 2, cy - tip)
        path.lineTo(cx, cy + tip)
        path.lineTo(cx + self._W / 2, cy - tip)
        p.drawPath(path)
        p.end()


# ----------------------------- 文本 -----------------------------------------
def page_title(text: str) -> QLabel:
    """页面大标题。三页都要有，缺一页就显得那页没做完。"""
    lb = QLabel(text)
    lb.setProperty("role", "page")
    return lb


def section_title(text: str) -> QLabel:
    """组标题。

    ⚠️ 用 ``sectionTitle``（14 Semibold，``text.primary``），比行标题**大一档**。
    规范点名禁止把组标题做成 caption、secondary 或弱灰文字——v2.0 正是 11px 弱灰，
    看起来比它下面的选项还弱。
    """
    lb = QLabel(text)
    lb.setProperty("role", "section")
    return lb


def note(text: str) -> QLabel:
    """组级说明，放在卡片下方，会换行。用 ``secondary``，不是 caption。

    行高靠富文本设定：Qt 的 QSS 不认 ``line-height``，富文本引擎认。
    """
    lb = QLabel()
    lb.setProperty("role", "secondary")
    lb.setWordWrap(True)
    lb.setTextFormat(Qt.TextFormat.RichText)
    lb.setText(theme.rich_text(text, theme.SECONDARY))
    return lb


def caption(text: str) -> QLabel:
    """时间戳、单位这类**真正**的辅助信息。别拿它当说明文字使。"""
    lb = QLabel(text)
    lb.setProperty("role", "caption")
    return lb


def body(text: str = "") -> QLabel:
    return QLabel(text)


def title(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setProperty("role", "title")
    return lb


class ElidedLabel(QLabel):
    """单行行内说明：装不下就从中间省略。

    行内说明**不能换行**。会换行的标签高度取决于宽度，窗口一窄就悄悄长成两三行，
    把整行顶高、连带把同一张卡片里别的行挤扁。路径这种长文本从中间省略最好认
    ——头上的盘符和尾巴上的文件名都留着。

    用 ``secondary``（12 / ``text.secondary``），不是 caption：规范的 Settings
    结构里行内说明就是 secondary，caption 只留给时间戳那一类。
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "secondary")
        self._full = text
        # 宽度 Ignored：行内说明再长也不该把行撑宽，缩就是了
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
        # 只有真省略了才挂 tooltip，短文本上冒一个同样的浮层是噪音。
        # Tooltip 只做补充，这里的完整文本在别处（配置页、日志）都拿得到。
        self.setToolTip(self._full if shown != self._full else "")


# ----------------------------- 卡片与行 -------------------------------------
class Card(QFrame):
    """设置组用的容器：``surface`` + ``radius.large``，行与行之间一条细分割线。

    规范把 Card 明确成正常的视觉组织工具：这几组设置在 canvas 上缺少边界，
    包起来之后层级和扫描都更清楚，属于「倾向使用 Card」的场景。
    起点是 surface + radius.large + 无阴影；因为 ``surface`` 与 ``canvas``
    的对比度低于 1.1:1，按规范补一条 ``separator.subtle`` 边界。

    分割线从**文字起始线**开始，不铺满整宽——铺满会切穿外圆角。
    """

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
        """插一个不带分割线的自定义块。"""
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


def _separator() -> QWidget:
    """左端缩进到文字起始线的分割线。"""
    holder = QWidget()
    holder.setObjectName("PageBody")
    box = QHBoxLayout(holder)
    box.setContentsMargins(theme.PADDING_CONTAINER, 0, 0, 0)
    line = QFrame()
    line.setObjectName("Separator")
    line.setFrameShape(QFrame.Shape.NoFrame)
    line.setFixedHeight(1)
    box.addWidget(line)
    holder.setFixedHeight(1)
    return holder


class Row(QWidget):
    """卡片里的一行：左边行标题（可带行内说明），右边控件。

    停用时**整行一起降级**——行标题也淡，不能只灰控件、文字仍然雪白。
    Qt 会把 disabled 往子部件传，样式表里 ``QLabel:disabled`` 接住，
    映射到 ``text.disabled``。规范禁止改用整行 Opacity。

    ⚠️ 高度**不要用** ``setMinimumHeight``。Qt 的 ``qSmartMinSize`` 里显式设过的
    最小高度会**顶掉**布局算出来的那个，于是页面一挤，行就被压到比内容还矮，
    行标题和说明直接叠在一起（v2.0 的「运行」页就是这么糊的）。地板加在标签上，
    行本身用 Fixed 的纵向策略，谁也压不动。
    """

    def __init__(self, label: str, sublabel: str = "",
                 parent: QWidget | None = None, *, inset: bool = True) -> None:
        """``inset=False`` 去掉左右内边距，给直接摆在对话框上、没有卡片包着的行用。"""
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        side = theme.PADDING_CONTAINER if inset else 0
        self._box = QHBoxLayout(self)
        self._box.setContentsMargins(side, theme.PADDING_CONTROL_Y,
                                     side, theme.PADDING_CONTROL_Y)
        self._box.setSpacing(theme.GAP_CONTROL)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(theme.GAP_RELATED)
        self.label = QLabel(label)
        text_col.addWidget(self.label)
        # 行内说明一律先建好再按需显示。只在有文案时才建，会让之后的
        # set_sublabel 悄悄没反应（v2.0 的「接入 start.bat」那行就一直空着）。
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
        """说明空着就整条藏掉，行高的地板改由行标题自己扛。

        地板跟着系统文本缩放走：字变大时行要跟着长，不能截断内容。
        """
        self.sublabel.setVisible(bool(text))
        floor = 0 if text else theme.scaled(
            theme.ROW_MIN_HEIGHT - theme.PADDING_CONTROL_Y * 2)
        self.label.setMinimumHeight(floor)


# ----------------------------- 统计块 ---------------------------------------
class StatTile(QFrame):
    """一个关键数字加一行说明。

    四个并排的汇总指标属于规范里「Dashboard 指标、摘要、重复对比单元」，
    倾向使用 Card：尺寸一致、可横向对比，包起来比散在 canvas 上好扫。
    """

    def __init__(self, caption_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        box = QVBoxLayout(self)
        box.setContentsMargins(theme.PADDING_CONTAINER, theme.PADDING_CONTAINER,
                               theme.PADDING_CONTAINER, theme.PADDING_CONTAINER)
        box.setSpacing(theme.GAP_RELATED)
        self.value = QLabel("0")
        self.value.setProperty("role", "metric")
        self.caption = QLabel(caption_text)
        self.caption.setProperty("role", "secondary")
        box.addWidget(self.value)
        box.addWidget(self.caption)

    def set_value(self, value: int | str) -> None:
        self.value.setText(str(value))

    def set_caption(self, text: str) -> None:
        self.caption.setText(text)


# ----------------------------- 曲线 -----------------------------------------
class DailyChart(QWidget):
    """每日 寸 / AJ / FC 三条折线。数据来自 ``classifier.daily_counts``。

    颜色用 ``viz.categorical``，不是语义色也不是品牌色——图表色板是与
    Neutral / Accent / Semantic 并列的第四套体系，单独生成。三个色相在色环上
    均匀分布，与 error / success / warning 以及品牌色相都至少差 20°，
    并且在三种色盲模拟下两两可辨。

    **颜色不是唯一区分手段**：每条线还带自己的线型和标记形状，图例上一模一样。
    """

    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 48, 18, 32, 42
    #: 三条序列的线型与标记，跟颜色一起构成区分。顺序固定。
    _STYLES = ((Qt.PenStyle.SolidLine, "circle"),
               (Qt.PenStyle.DashLine, "square"),
               (Qt.PenStyle.DotLine, "triangle"))
    _NAMES = ("寸", "AJ", "FC")

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
            p.setPen(theme.qcolor("text.secondary"))
            p.setFont(theme.font(theme.BODY))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "还没有记录。启动监视或做一次全量扫描就会有数据。")
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

        # 网格与纵轴刻度。网格线不承担状态表达，不要求 3:1。
        p.setFont(theme.font(theme.CAPTION))
        grid, axis = theme.qcolor("viz.grid"), theme.qcolor("viz.axis")
        steps = min(5, y_top)
        for s in range(steps + 1):
            v = y_top * s / steps
            y = ypos(v)
            p.setPen(QPen(grid, 1))
            p.drawLine(int(self._PAD_L), int(y), int(w - self._PAD_R), int(y))
            p.setPen(axis)
            p.drawText(0, int(y) - 8, self._PAD_L - 8, 16,
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       str(round(v)))

        for series, idx in enumerate((1, 2, 3)):
            self._draw_series(p, series, idx, xpos, ypos)

        # 横轴：首、中、末三个日期，密了也不会糊成一片
        p.setPen(axis)
        marks = {0, len(self._data) // 2, len(self._data) - 1}
        for i in sorted(marks):
            label = self._data[i][0][5:]
            p.drawText(int(xpos(i)) - 28, h - self._PAD_B + 8, 56, 18,
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                       label)

        # 图例：线型和标记跟绘制时一致，顺序也一致
        x = self._PAD_L
        for series, name in enumerate(self._NAMES):
            color = QColor(theme.viz_series(series))
            style, marker = self._STYLES[series]
            p.setPen(QPen(color, 2, style))
            p.drawLine(int(x), 16, int(x) + 18, 16)
            self._marker(p, color, marker, x + 9, 16)
            p.setPen(theme.qcolor("text.secondary"))
            p.drawText(int(x) + 24, 8, 40, 16,
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), name)
            x += 74
        p.end()

    def _draw_series(self, p: QPainter, series: int, idx: int, xpos, ypos) -> None:
        color = QColor(theme.viz_series(series))
        style, marker = self._STYLES[series]
        path = QPainterPath()
        for i, row in enumerate(self._data):
            x, y = xpos(i), ypos(row[idx])
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(color, 2, style))
        p.drawPath(path)

        if len(self._data) <= 60:        # 点太多就只留线，不然是一条毛毛虫
            for i, row in enumerate(self._data):
                self._marker(p, color, marker, xpos(i), ypos(row[idx]))

    @staticmethod
    def _marker(p: QPainter, color: QColor, kind: str, x: float, y: float) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        if kind == "circle":
            p.drawEllipse(QRectF(x - 3, y - 3, 6, 6))
        elif kind == "square":
            p.drawRect(QRectF(x - 2.6, y - 2.6, 5.2, 5.2))
        else:
            tri = QPainterPath()
            tri.moveTo(x, y - 3.4)
            tri.lineTo(x + 3.2, y + 2.6)
            tri.lineTo(x - 3.2, y + 2.6)
            tri.closeSubpath()
            p.fillPath(tri, color)


# ----------------------------- 浮动提示 -------------------------------------
class Toast(QFrame):
    """盖在内容上方的一条提示。

    悬浮而不占布局位置，出现和消失都不会让页面重排。

    严重度不只靠颜色：每条 Toast 都有一句把结果说清楚的标题（「已保存」
    「扫描出错」），文字才是主要载体，左边那条色带是补充。

    **错误不自动消失**，留一个关闭按钮——规范要求错误提示保留到用户处理或关闭。
    """

    INFO, SUCCESS, WARNING, ERROR = "info", "success", "warning", "error"
    #: 简短成功信息约 2s；错误由用户关闭。
    SHORT_MS = 2000

    closed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setVisible(False)
        box = QHBoxLayout(self)
        box.setContentsMargins(theme.PADDING_CONTAINER, theme.PADDING_CONTROL_Y,
                               theme.PADDING_CONTROL_Y, theme.PADDING_CONTROL_Y)
        box.setSpacing(theme.GAP_INLINE)

        self._bar = QFrame(self)
        self._bar.setFixedWidth(3)
        self._bar.setFrameShape(QFrame.Shape.NoFrame)
        box.addWidget(self._bar)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(theme.GAP_RELATED)
        self._title = QLabel("")
        self._message = QLabel("")
        self._message.setProperty("role", "secondary")
        self._message.setWordWrap(True)
        text_col.addWidget(self._title)
        text_col.addWidget(self._message)
        box.addLayout(text_col, 1)

        # 可执行的恢复动作（撤销之类）。规范：能提供 Undo 时优先 Undo。
        self._action = QPushButton("")
        self._action.setProperty("role", "quiet")
        self._action.clicked.connect(self._run_action)
        self._action.hide()
        box.addWidget(self._action, 0, Qt.AlignmentFlag.AlignTop)

        self._close = QPushButton("关闭")
        self._close.setProperty("role", "quiet")
        self._close.clicked.connect(self.hide_toast)
        box.addWidget(self._close, 0, Qt.AlignmentFlag.AlignTop)
        self._on_action = None

        theme.apply_shadow(self)                     # Elevated Surface：无边框，靠阴影
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_toast)

    def show_toast(self, title_text: str, message: str,
                   severity: str = INFO, duration_ms: int | None = None,
                   action: tuple[str, object] | None = None) -> None:
        self._title.setText(title_text)
        self._message.setText(message)
        color = theme.color(f"semantic.{severity}.solid"
                            if severity in (self.SUCCESS, self.WARNING, self.ERROR)
                            else "semantic.info.solid")
        self._bar.setStyleSheet(f"background: {color}; border-radius: 1px;")

        self._on_action = action[1] if action else None
        self._action.setText(action[0] if action else "")
        self._action.setVisible(action is not None)

        # 错误留到用户处理或关闭；带动作的也别急着收走，不然撤销按钮一闪就没。
        persistent = severity == self.ERROR or action is not None
        self._close.setVisible(persistent)
        self.adjustSize()
        self._reposition()
        self.setVisible(True)
        self.raise_()
        self._timer.stop()
        if not persistent:
            self._timer.start(duration_ms or self.SHORT_MS)

    def hide_toast(self) -> None:
        self._timer.stop()
        self._on_action = None
        self.setVisible(False)
        self.closed.emit()

    def _run_action(self) -> None:
        callback, self._on_action = self._on_action, None
        self.hide_toast()
        if callable(callback):
            callback()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = theme.PADDING_PAGE_X
        width = min(max(self.sizeHint().width(), 360),
                    max(360, parent.width() - margin * 2))
        self.setFixedWidth(width)
        self.adjustSize()
        self.move((parent.width() - self.width()) // 2, theme.SPACE_3)

    def parent_resized(self) -> None:
        if self.isVisible():
            self._reposition()
