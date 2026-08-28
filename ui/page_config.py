# -*- coding: utf-8 -*-
"""「配置」页：目录、判定规则、整理、DGHub 联动、自动截图。

界面上的值不会自动写回配置文件——:meth:`ConfigPage.read_into` 由主窗口在
「保存配置」/「应用并重新扫描」时调用，一次性收走全部改动。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from core.config import ranks
from core.models import MAX_SCORE, Category, CunConfig, OrganizeStep

from . import theme, widgets
from .rule_dialog import RuleDialog
from .widgets import Card, Combo, Row, Switch

if TYPE_CHECKING:                                   # 只为类型标注，运行时不导入主窗口
    from .main_window import MainWindow

_SPAN_KEYS = ("year", "month", "day")
_SPAN_NAMES = ("按年", "按月", "按日")

_ORGANIZE_LABELS = {
    "date": "根据日期整理",
    "rank": "根据评级整理",
    "achievement": "根据达成整理（AJ / FC / 普通）",
}


class _RuleRefs(NamedTuple):
    switch: Switch
    lo: QSpinBox | None
    m_hi: QSpinBox | None
    a_hi: QSpinBox | None
    rank: Combo | None


class _OrgRefs(NamedTuple):
    kind: str
    switch: Switch
    span: Combo | None


class ConfigPage(QWidget):
    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        self._rules: dict[str, _RuleRefs] = {}
        self._org_rows: list[tuple[QWidget, _OrgRefs]] = []

        self._body = widgets.page_shell(self)
        self._body.addWidget(widgets.page_title("配置"))
        self._body.addSpacing(theme.GRID)

        self._build_dirs()
        self._build_rules()
        self._build_organize()
        self._build_link()
        self._build_capture()
        self._build_actions()
        self._body.addStretch(1)

    def _section(self, title: str) -> None:
        if self._body.count():
            self._body.addSpacing(theme.GRID * 3)
        self._body.addWidget(widgets.section_title(title))

    def _note(self, text: str) -> None:
        self._body.addWidget(widgets.caption(text))

    # ----------------------------- 目录 -------------------------------------
    def _build_dirs(self) -> None:
        cfg = self._main.cfg
        self._section("目录")
        card = Card()

        self.game_box, game_row = self._dir_row("游戏目录", cfg.game_root, self._browse_game)
        card.add_row(game_row)
        self.shots_box, shots_row = self._dir_row("截图目录", cfg.screenshots_dir, self._browse_shots)
        card.add_row(shots_row)
        self.out_box, out_row = self._dir_row("输出目录", cfg.output_root, self._browse_out)
        card.add_row(out_row)

        self._body.addWidget(card)
        self._note("截图目录是要扫描的原始截图所在文件夹，输出目录是分类结果的根目录，"
                   "「寸」等子文件夹建在那里。游戏目录用来定位截图目录和 start.bat，"
                   "换了游戏安装位置就在这里改。")

    def _dir_row(self, label: str, value: str, on_browse) -> tuple[QLineEdit, Row]:
        row = Row(label)
        box = QLineEdit(value)
        box.setReadOnly(True)
        box.setProperty("role", "path")
        box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        box.setMinimumWidth(320)
        browse = QPushButton("浏览…")
        browse.clicked.connect(on_browse)
        row.add(box, browse)
        return box, row

    def _browse_game(self) -> None:
        path = self._main.pick_folder("选择 CHUNITHM 游戏目录")
        if not path:
            return
        from core.config import derive_paths, normalize_game_root
        root = normalize_game_root(path)
        if root is None:
            self._main.show_toast("这个目录不像游戏目录",
                                  "选中 CHUNITHM 根目录（里面有 bin 文件夹）或它的 bin 目录。",
                                  widgets.Toast.WARNING, 5000)
            return
        self.game_box.setText(str(root))
        shots, bat = derive_paths(root)
        self.shots_box.setText(shots)
        if not self.out_box.text().strip():
            self.out_box.setText(shots)
        if bat:
            self._main.cfg.start_bat = bat
        self._main.show_toast("已定位游戏目录", str(root), widgets.Toast.SUCCESS)

    def _browse_shots(self) -> None:
        path = self._main.pick_folder("选择截图目录")
        if not path:
            return
        self.shots_box.setText(path)
        # 第一次选输入目录时把输出也指过去，分类结果就落在原图旁边（一直以来的默认）
        if not self.out_box.text().strip():
            self.out_box.setText(path)

    def _browse_out(self) -> None:
        path = self._main.pick_folder("选择输出目录")
        if path:
            self.out_box.setText(path)

    # ----------------------------- 判定规则 ---------------------------------
    def _build_rules(self) -> None:
        self._section("判定规则（「寸」统计）")
        self._rules_card = Card()
        for cat in self._main.cfg.categories:
            self._rules_card.add_row(self._rule_row(cat))
        self._rules_card.add_row(self._add_rule_row())
        self._body.addWidget(self._rules_card)
        self._note("命中的截图会被复制到规则的输出文件夹并计入统计，原图留在原地。"
                   "一张图可以同时命中多条规则。")

    def _rule_row(self, cat: Category) -> Row:
        row = Row(cat.label or cat.key, "→ " + cat.folder)
        lo = m_hi = a_hi = None
        rank = None

        if cat.kind == "score":
            lo = _spin(0, cat.hi or MAX_SCORE, cat.lo or 0, width=120)
            row.add(QLabel("得分"), lo, QLabel(f"~ {cat.hi or 0:,}"))
        elif cat.kind == "ajcun":
            m_hi = _spin(0, 100, cat.m_hi if cat.m_hi is not None else 4)
            row.add(QLabel("0 < MISS ≤"), m_hi)
        elif cat.kind == "am":
            a_hi = _spin(0, 100, cat.a_hi if cat.a_hi is not None else 4)
            m_hi = _spin(0, 100, cat.m_hi if cat.m_hi is not None else 4)
            rank = Combo()
            for r in ranks(self._main.cfg):
                rank.addItem(r)
            idx = rank.findText(cat.min_rank or "SSS")
            if idx >= 0:
                rank.setCurrentIndex(idx)
            row.add(QLabel("ATTACK ≤"), a_hi, QLabel("MISS ≤"), m_hi, QLabel("且评级 ≥"), rank)

        switch = Switch()
        switch.setChecked(cat.enabled)
        row.add(switch)

        delete = QPushButton("✕")
        delete.setProperty("role", "remove")
        delete.setToolTip("删除这条判定规则")
        delete.clicked.connect(lambda: self._remove_rule(cat))
        row.add(delete)

        self._rules[cat.key] = _RuleRefs(switch, lo, m_hi, a_hi, rank)
        return row

    def _add_rule_row(self) -> Row:
        row = Row("自定义判定")
        button = QPushButton("添加判定规则")
        button.clicked.connect(self._add_rule)
        row.add(button)
        return row

    def _add_rule(self) -> None:
        dialog = RuleDialog(self._main.cfg, {c.key for c in self._main.cfg.categories}, self)
        if not dialog.exec():
            return
        cat = dialog.result_category()
        self._main.cfg.categories.append(cat)
        self._rebuild_rules()
        self._main.show_toast("已添加", f"「{cat.label}」已加入判定规则，记得点「保存配置」",
                              widgets.Toast.SUCCESS)

    def _remove_rule(self, cat: Category) -> None:
        try:
            self._main.cfg.categories.remove(cat)
        except ValueError:
            return
        self._rules.pop(cat.key, None)
        self._rebuild_rules()

    def _rebuild_rules(self) -> None:
        self._rules.clear()
        self._rules_card.clear()
        for cat in self._main.cfg.categories:
            self._rules_card.add_row(self._rule_row(cat))
        self._rules_card.add_row(self._add_rule_row())

    # ----------------------------- 整理 -------------------------------------
    def _build_organize(self) -> None:
        self._section("整理（移动原图归档）")
        self._org_card = Card()
        self._rebuild_organize(self._main.cfg.organize.steps)
        self._body.addWidget(self._org_card)
        self._note("靠上的维度是外层文件夹：「日期」在上、「评级」在下，归档路径就是"
                   "「日期/评级/图.png」。开启任一项之后，扫描会把识别出成绩的原图"
                   "移动到对应文件夹，无关图片不动。原图只是换了位置，没有删除。")

    def _rebuild_organize(self, steps: list[OrganizeStep]) -> None:
        self._org_rows.clear()
        self._org_card.clear()
        for step in steps:
            row = Row(_ORGANIZE_LABELS.get(step.kind, step.kind))
            span = None
            if step.kind == "date":
                span = Combo()
                for name in _SPAN_NAMES:
                    span.addItem(name)
                span.setCurrentIndex(max(0, _SPAN_KEYS.index(step.date_span)
                                         if step.date_span in _SPAN_KEYS else 1))
                row.add(span)

            up = QPushButton("↑")
            up.setProperty("role", "quiet")
            up.setToolTip("上移一层")
            down = QPushButton("↓")
            down.setProperty("role", "quiet")
            down.setToolTip("下移一层")
            switch = Switch()
            switch.setChecked(step.enabled)
            row.add(up, down, switch)

            refs = _OrgRefs(step.kind, switch, span)
            up.clicked.connect(lambda _=False, k=step.kind: self._move_organize(k, -1))
            down.clicked.connect(lambda _=False, k=step.kind: self._move_organize(k, +1))

            self._org_card.add_row(row)
            self._org_rows.append((row, refs))

    def _move_organize(self, kind: str, delta: int) -> None:
        steps = self._current_organize_steps()
        i = next((n for n, s in enumerate(steps) if s.kind == kind), -1)
        j = i + delta
        if i < 0 or not 0 <= j < len(steps):
            return
        steps[i], steps[j] = steps[j], steps[i]
        self._rebuild_organize(steps)

    def _current_organize_steps(self) -> list[OrganizeStep]:
        steps: list[OrganizeStep] = []
        for _row, refs in self._org_rows:
            step = OrganizeStep(kind=refs.kind, enabled=refs.switch.isChecked())
            if refs.span is not None:
                step.date_span = _SPAN_KEYS[max(0, refs.span.currentIndex())]
            steps.append(step)
        return steps

    # ----------------------------- 联动 -------------------------------------
    def _build_link(self) -> None:
        cfg = self._main.cfg
        self._section("DGHub 联动")
        card = Card()

        enable_row = Row("启用 DGHub 联动")
        self.dg_switch = Switch()
        self.dg_switch.setChecked(cfg.dghub.enabled)
        enable_row.add(self.dg_switch)
        card.add_row(enable_row)

        port_row = Row("本机数据端口", "与插件配置里的端点保持一致")
        self.dg_port = _spin(1, 65535, cfg.dghub.port or 8890, width=110)
        port_row.add(self.dg_port)
        card.add_row(port_row)

        self._body.addWidget(card)
        self._note("开启后从游戏内存实时读取判定计数（只读，不修改游戏），在本机提供数据服务，"
                   "由 DGHub 里的「今天你寸了吗 · 联动」插件读取并触发波形。"
                   "MISS / ATTACK / 结算的强度、波形预设、通道都在 DGHub 的插件配置页里调；"
                   "结算是否「寸了」按上面的判定规则算。保存后立即生效。")

    # ----------------------------- 自动截图 ---------------------------------
    def _build_capture(self) -> None:
        cfg = self._main.cfg
        self._section("自动截图（结算画面）")
        card = Card()

        enable_row = Row("启用自动截图")
        self.cap_switch = Switch()
        self.cap_switch.setChecked(cfg.capture.enabled)
        enable_row.add(self.cap_switch)
        card.add_row(enable_row)

        delay_row = Row("识别到结算画面后等待", "等分数滚完再存")
        self.cap_delay = QDoubleSpinBox()
        self.cap_delay.setRange(0.0, 15.0)
        self.cap_delay.setSingleStep(0.5)
        self.cap_delay.setDecimals(1)
        self.cap_delay.setSuffix(" 秒")
        self.cap_delay.setValue(cfg.capture.delay_s)
        self.cap_delay.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.cap_delay.setMinimumWidth(100)
        delay_row.add(self.cap_delay)
        card.add_row(delay_row)

        self._body.addWidget(card)
        self._note("由本程序在每首歌结算时自动截取游戏画面存进截图目录，判定数据直接取自内存，"
                   "新截图不再需要 OCR，原来的外部截图工具可以停用。依赖游戏内存读取，"
                   "本开关或上面的 DGHub 联动任一开启即生效。历史截图重扫仍然走 OCR。")

    # ----------------------------- 按钮 -------------------------------------
    def _build_actions(self) -> None:
        self._body.addSpacing(theme.GRID * 2)
        bar = QHBoxLayout()
        bar.setSpacing(theme.GRID)

        open_btn = QPushButton("打开输出文件夹")
        open_btn.clicked.connect(self._main.open_output)
        bar.addWidget(open_btn)
        bar.addStretch(1)

        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._main.save_config_from_ui)
        bar.addWidget(save_btn)

        rescan_btn = QPushButton("应用并重新扫描")
        rescan_btn.setProperty("role", "accent")
        rescan_btn.clicked.connect(self._main.apply_and_rescan)
        bar.addWidget(rescan_btn)

        holder = QWidget()
        holder.setObjectName("PageBody")
        holder.setLayout(bar)
        self._body.addWidget(holder)

    # ----------------------------- 读回 -------------------------------------
    def read_into(self, cfg: CunConfig) -> None:
        """把界面上的当前状态收进配置对象。"""
        cfg.game_root = self.game_box.text().strip()
        cfg.screenshots_dir = self.shots_box.text().strip()
        cfg.output_root = self.out_box.text().strip()

        cfg.dghub.enabled = self.dg_switch.isChecked()
        cfg.dghub.port = self.dg_port.value()
        cfg.capture.enabled = self.cap_switch.isChecked()
        cfg.capture.delay_s = self.cap_delay.value()

        steps = self._current_organize_steps()
        if steps:
            cfg.organize.steps = steps

        for cat in cfg.categories:
            refs = self._rules.get(cat.key)
            if refs is None:
                continue
            cat.enabled = refs.switch.isChecked()
            if cat.kind == "score" and refs.lo is not None:
                cat.lo = refs.lo.value()            # 上限由预设锁死，不跟着改
            elif cat.kind == "ajcun" and refs.m_hi is not None:
                cat.m_hi = refs.m_hi.value()
            elif cat.kind == "am":
                if refs.a_hi is not None:
                    cat.a_hi = refs.a_hi.value()
                if refs.m_hi is not None:
                    cat.m_hi = refs.m_hi.value()
                if refs.rank is not None:
                    cat.min_rank = refs.rank.currentText()
                cat.score_min = None                # am 用 min_rank，清掉遗留键

    def refresh_paths(self) -> None:
        """配置在别处被改过（比如首次运行向导）之后，把目录框刷新一遍。"""
        cfg = self._main.cfg
        self.game_box.setText(cfg.game_root)
        self.shots_box.setText(cfg.screenshots_dir)
        self.out_box.setText(cfg.output_root)


def _spin(minimum: int, maximum: int, value: int, width: int = 80) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    box.setGroupSeparatorShown(maximum > 1000)
    box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    box.setFixedWidth(width)
    box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return box
