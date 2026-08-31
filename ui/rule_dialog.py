# -*- coding: utf-8 -*-
"""「添加判定规则」对话框。

三种类型：评级判定（按得分区间）、AJ寸、ATTACK+MISS。选评级判定时再出一个
档位下拉，选中某个预设则上限锁死、下限仍可调；选「自定义区间」上下限都能填。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from core.config import SCORE_PRESETS, ranks
from core.models import MAX_SCORE, Category, CunConfig

from . import theme, widgets

_KINDS: tuple[tuple[str, str], ...] = (
    ("score", "评级判定"),
    ("ajcun", "AJ寸（A=0，0<MISS≤x）"),
    ("am", "ATTACK+MISS（A≤a，M≤m，评级≥）"),
)

_CUSTOM_RANGE = "自定义区间"


class RuleDialog(QDialog):
    """填完点「添加」，用 :meth:`result_category` 取结果。"""

    def __init__(self, cfg: CunConfig, existing_keys: set[str],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._existing = existing_keys
        self.setWindowTitle("添加判定规则")
        self.setMinimumWidth(460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PADDING_PAGE_X, theme.PADDING_PAGE_Y,
                                 theme.PADDING_PAGE_X, theme.PADDING_PAGE_Y)
        outer.setSpacing(theme.GAP_GROUP)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(theme.GAP_GROUP)
        form.setVerticalSpacing(theme.GAP_CONTROL)

        self.name_box = QLineEdit()
        self.name_box.setPlaceholderText("例如：SSS寸")
        form.addRow("名称", self.name_box)

        self.kind_box = widgets.Combo()
        for _, label in _KINDS:
            self.kind_box.addItem(label)
        form.addRow("判定类型", self.kind_box)

        self.preset_box = widgets.Combo()
        for name, _, _ in SCORE_PRESETS:
            self.preset_box.addItem(name)
        self.preset_box.addItem(_CUSTOM_RANGE)
        self.preset_row_label = QLabel("评级档位")
        form.addRow(self.preset_row_label, self.preset_box)

        self.lo_box = _spin(0, MAX_SCORE)
        self.lo_label = QLabel("得分下限")
        form.addRow(self.lo_label, self.lo_box)

        self.hi_box = _spin(0, MAX_SCORE)
        self.hi_fixed = QLabel("")
        self.hi_label = QLabel("得分上限")
        hi_holder = QWidget()
        hi_layout = QHBoxLayout(hi_holder)
        hi_layout.setContentsMargins(0, 0, 0, 0)
        hi_layout.addWidget(self.hi_box)
        hi_layout.addWidget(self.hi_fixed)
        form.addRow(self.hi_label, hi_holder)

        self.a_hi_box = _spin(0, 100, 4)
        self.a_hi_label = QLabel("ATTACK 上限")
        form.addRow(self.a_hi_label, self.a_hi_box)

        self.m_hi_box = _spin(0, 100, 4)
        self.m_hi_label = QLabel("MISS 上限")
        form.addRow(self.m_hi_label, self.m_hi_box)

        self.rank_box = widgets.Combo()
        for r in ranks(cfg):
            self.rank_box.addItem(r)
        idx = self.rank_box.findText("SSS")
        if idx >= 0:
            self.rank_box.setCurrentIndex(idx)
        self.rank_label = QLabel("评级 ≥")
        form.addRow(self.rank_label, self.rank_box)

        self.folder_box = QLineEdit()
        self.folder_box.setPlaceholderText("寸/名称")
        form.addRow("输出文件夹", self.folder_box)
        self._form = form
        outer.addLayout(form)

        outer.addWidget(widgets.note(
            "留空的输出文件夹等于「寸/名称」。命中的截图会被复制到那里，原图不动。"))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(theme.GAP_CONTROL)
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        add = QPushButton("添加")
        add.setProperty("role", "accent")
        add.setDefault(True)
        add.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(add)
        outer.addLayout(buttons)

        # 对话框是独立的顶层窗口，焦点环要自己装一个
        self._focus_ring = widgets.FocusRing(self)

        self._last_suggest = ""
        self.kind_box.currentIndexChanged.connect(self._refresh)
        self.preset_box.currentIndexChanged.connect(self._refresh)
        self._refresh()

    # ----------------------------- 联动 -------------------------------------
    def _kind(self) -> str:
        return _KINDS[self.kind_box.currentIndex()][0]

    def _is_custom_range(self) -> bool:
        return self.preset_box.currentText() == _CUSTOM_RANGE

    def _refresh(self) -> None:
        kind = self._kind()
        is_score = kind == "score"
        custom = self._is_custom_range()

        # QFormLayout.setRowVisible 会连标签一起收掉，不留空行
        self._form.setRowVisible(self.preset_box, is_score)
        self._form.setRowVisible(self.lo_box, is_score)
        self._form.setRowVisible(self.hi_box.parentWidget(), is_score)
        self.hi_box.setVisible(is_score and custom)
        self.hi_fixed.setVisible(is_score and not custom)

        self._form.setRowVisible(self.m_hi_box, kind in ("ajcun", "am"))
        self._form.setRowVisible(self.a_hi_box, kind == "am")
        self._form.setRowVisible(self.rank_box, kind == "am")

        if is_score and not custom:
            _, lo, hi = SCORE_PRESETS[self.preset_box.currentIndex()]
            self.lo_box.setMaximum(hi)
            self.lo_box.setValue(lo)
            self.hi_fixed.setText(f"{hi:,}（固定）")
        elif is_score:
            self.lo_box.setMaximum(MAX_SCORE)

        self._suggest_name()

    def _suggest_name(self) -> None:
        """名字跟着当前选择自动填，用户一旦自己打过就不再覆盖。"""
        kind = self._kind()
        if kind == "score":
            suggestion = None if self._is_custom_range() else self.preset_box.currentText()
        elif kind == "ajcun":
            suggestion = "AJ寸"
        else:
            suggestion = "AM寸"
        if suggestion is None:
            return
        current = self.name_box.text().strip()
        if not current or current == self._last_suggest:
            self.name_box.setText(suggestion)
            self._last_suggest = suggestion

    # ----------------------------- 结果 -------------------------------------
    def _unique_key(self, label: str) -> str:
        base = label.strip() or "custom"
        key = base
        i = 2
        while key in self._existing:
            key = f"{base}_{i}"
            i += 1
        return key

    def _accept(self) -> None:
        if not self.name_box.text().strip():
            self.name_box.setFocus()
            return
        self.accept()

    def result_category(self) -> Category:
        label = self.name_box.text().strip()
        kind = self._kind()
        folder = self.folder_box.text().strip() or f"寸/{label}"
        cat = Category(key=self._unique_key(label), label=label, kind=kind,
                       enabled=True, custom=True, folder=folder)
        if kind == "score":
            if self._is_custom_range():
                cat.lo = self.lo_box.value()
                cat.hi = self.hi_box.value()
            else:
                _, _, hi = SCORE_PRESETS[self.preset_box.currentIndex()]
                cat.lo = self.lo_box.value()
                cat.hi = hi
        elif kind == "ajcun":
            cat.m_hi = self.m_hi_box.value()
        else:
            cat.a_hi = self.a_hi_box.value()
            cat.m_hi = self.m_hi_box.value()
            cat.min_rank = self.rank_box.currentText()
        return cat


def _spin(minimum: int, maximum: int, value: int = 0) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    box.setGroupSeparatorShown(maximum > 1000)
    box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    box.setMinimumWidth(120)
    return box
