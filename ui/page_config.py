# -*- coding: utf-8 -*-
"""「配置」页：目录、判定规则、整理、DGHub 联动、自动截图、外观。

**保存边界**（规范 5.2）：开关、单选和选择器改完**立即生效并写盘**；目录、
端口、秒数、得分阈值这些输入字段属于多字段表单，要点「保存配置」才提交。
界面上在按钮旁边把这条边界写出来了——规范不允许混用两种保存方式而不说明。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QWidget)

from core.config import ranks
from core.models import MAX_SCORE, Category, CunConfig, OrganizeStep

from . import theme, widgets
from .rule_dialog import RuleDialog
from .widgets import Card, Combo, IconButton, Row, Segmented, Switch, Toast

if TYPE_CHECKING:                                   # 只为类型标注，运行时不导入主窗口
    from .main_window import MainWindow

_SPAN_KEYS = ("year", "month", "day")
_SPAN_NAMES = ("年", "月", "日")

#: 维度名就是维度名，取值枚举放在组级说明里，不塞进标签
_ORGANIZE_LABELS = {"date": "日期", "rank": "评级", "achievement": "达成"}


class _RuleRefs(NamedTuple):
    switch: Switch
    lo: QSpinBox | None
    m_hi: QSpinBox | None
    a_hi: QSpinBox | None
    rank: Combo | None


class _OrgRefs(NamedTuple):
    kind: str
    switch: Switch
    span: Segmented | None


class ConfigPage(QWidget):
    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        self._rules: dict[str, _RuleRefs] = {}
        self._org_rows: list[tuple[QWidget, _OrgRefs]] = []
        self._loading = True

        self._body = widgets.page_shell(self)
        self._body.addWidget(widgets.page_title("配置"))
        self._body.addSpacing(theme.PAGE_TITLE_TO_SECTION)
        self._first_section = True

        self._build_dirs()
        self._build_rules()
        self._build_organize()
        self._build_link()
        self._build_capture()
        self._build_appearance()
        self._build_actions()
        self._body.addStretch(1)
        self._loading = False

    # ----------------------------- 版式 -------------------------------------
    def _section(self, title: str) -> None:
        """组标题。两个 Section 之间固定 gap.section，标题到卡片 8。"""
        if not self._first_section:
            self._body.addSpacing(theme.GAP_SECTION)
        self._first_section = False
        self._body.addWidget(widgets.section_title(title))
        self._body.addSpacing(theme.SECTION_TITLE_TO_CARD)

    def _note(self, text: str) -> None:
        """组级说明，放在卡片下方。"""
        self._body.addSpacing(theme.CARD_TO_NOTE)
        self._body.addWidget(widgets.note(text))

    def _autosave(self) -> None:
        """开关 / 选择器改完立刻落盘。构建界面时的程序化置位不算。"""
        if not self._loading:
            self._main.save_instant_settings()

    # ----------------------------- 目录 -------------------------------------
    def _build_dirs(self) -> None:
        cfg = self._main.cfg
        self._section("目录")
        card = Card()

        self.game_box, game_row = self._dir_row("游戏目录", cfg.game_root, self._browse_game)
        card.add_row(game_row)
        self.shots_box, shots_row = self._dir_row("截图目录", cfg.screenshots_dir,
                                                  self._browse_shots)
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
                                  Toast.WARNING)
            return
        self.game_box.setText(str(root))
        shots, bat = derive_paths(root)
        self.shots_box.setText(shots)
        if not self.out_box.text().strip():
            self.out_box.setText(shots)
        if bat:
            self._main.cfg.start_bat = bat
        self._main.show_toast("已定位游戏目录", str(root), Toast.SUCCESS)

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
        self._section("判定规则")
        self._rules_card = Card()
        self._rebuild_rules()
        self._body.addWidget(self._rules_card)
        self._note("命中的截图会被复制到规则的输出文件夹并计入「寸」统计，原图留在原地。"
                   "一张图可以同时命中多条规则。开关立即生效；区间和阈值改完要点「保存配置」。")

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
            row.add(QLabel("ATTACK ≤"), a_hi, QLabel("MISS ≤"), m_hi,
                    QLabel("且评级 ≥"), rank)

        switch = Switch()
        switch.setChecked(cat.enabled)
        switch.setAccessibleName(f"启用判定规则 {cat.label or cat.key}")
        switch.toggled.connect(self._autosave)
        row.add(switch)

        # 破坏性动作要有常驻文字。一个光秃秃的 ✕ 只在指针悬停时才说得清自己是什么，
        # 触屏和键盘用户拿不到那句话。
        delete = QPushButton("删除")
        delete.setProperty("role", "destructive")
        delete.clicked.connect(lambda: self._remove_rule(cat))
        row.add(delete)

        self._rules[cat.key] = _RuleRefs(switch, lo, m_hi, a_hi, rank)
        return row

    def _add_rule_row(self) -> Row:
        """一条规则都没有时，这一行同时承担 Empty 状态：说清现状和下一步。"""
        if self._main.cfg.categories:
            row = Row("自定义判定")
        else:
            row = Row("还没有判定规则",
                      "添加一条之后，命中的截图会被复制到「寸」文件夹并计入统计")
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
        self._main.save_instant_settings()
        self._main.show_toast("已添加", f"判定规则「{cat.label}」已生效", Toast.SUCCESS)

    def _remove_rule(self, cat: Category) -> None:
        """删规则给撤销，不弹确认。

        规范：能提供 Undo 时优先 Undo，避免频繁确认。这个动作本身可恢复——
        原图不受影响，只是之后不再往那个文件夹复制。
        """
        try:
            index = self._main.cfg.categories.index(cat)
        except ValueError:
            return
        self._main.cfg.categories.pop(index)
        self._rules.pop(cat.key, None)
        self._rebuild_rules()
        self._main.save_instant_settings()

        def undo() -> None:
            self._main.cfg.categories.insert(
                min(index, len(self._main.cfg.categories)), cat)
            self._rebuild_rules()
            self._main.save_instant_settings()
            self._main.show_toast("已恢复", f"判定规则「{cat.label or cat.key}」回来了",
                                  Toast.SUCCESS)

        self._main.show_toast(
            "已删除判定规则",
            f"「{cat.label or cat.key}」不再参与判定。已归档的截图不受影响。",
            Toast.INFO, action=("撤销", undo))

    def _rebuild_rules(self) -> None:
        self._rules.clear()
        self._rules_card.clear()
        was, self._loading = self._loading, True     # 重建时的置位不该触发保存
        for cat in self._main.cfg.categories:
            self._rules_card.add_row(self._rule_row(cat))
        self._rules_card.add_row(self._add_rule_row())
        self._loading = was

    # ----------------------------- 整理 -------------------------------------
    def _build_organize(self) -> None:
        self._section("整理")
        self._org_card = Card()
        self._rebuild_organize(self._main.cfg.organize.steps)
        self._body.addWidget(self._org_card)
        self._note("开启任一项之后，扫描会把识别出成绩的原图移动到对应文件夹；"
                   "原图只是换了位置，没有删除，无关图片不动。靠上的维度是外层文件夹："
                   "「日期」在上、「评级」在下，归档路径就是「日期/评级/图.png」。"
                   "达成分为 AJ、FC、普通三档。")

    def _rebuild_organize(self, steps: list[OrganizeStep]) -> None:
        was, self._loading = self._loading, True
        self._org_rows.clear()
        self._org_card.clear()
        last = len(steps) - 1
        for i, step in enumerate(steps):
            name = _ORGANIZE_LABELS.get(step.kind, step.kind)
            row = Row(name)
            span = None
            if step.kind == "date":
                # 三项互斥、标签极短、需要直接比较 → Segmented，不用下拉框
                span = Segmented(_SPAN_NAMES)
                span.set_current(_SPAN_KEYS.index(step.date_span)
                                 if step.date_span in _SPAN_KEYS else 1)
                span.changed.connect(self._autosave)
                row.add(span)

            # 换顺序是高频、无破坏性、含义明确的动作，可以只用图标。
            # 头尾两端把不可能的方向停用掉——图标按钮点下去毫无反应，
            # 比文字按钮更让人以为是坏的。
            up = IconButton(IconButton.UP, f"把「{name}」上移一层")
            up.setEnabled(i > 0)
            down = IconButton(IconButton.DOWN, f"把「{name}」下移一层")
            down.setEnabled(i < last)
            switch = Switch()
            switch.setChecked(step.enabled)
            switch.setAccessibleName(f"启用按{name}整理")
            switch.toggled.connect(self._autosave)
            row.add(up, down, switch)

            refs = _OrgRefs(step.kind, switch, span)
            up.clicked.connect(lambda _=False, k=step.kind: self._move_organize(k, -1))
            down.clicked.connect(lambda _=False, k=step.kind: self._move_organize(k, +1))

            self._org_card.add_row(row)
            self._org_rows.append((row, refs))
        self._loading = was

    def _move_organize(self, kind: str, delta: int) -> None:
        steps = self.current_organize_steps()
        i = next((n for n, s in enumerate(steps) if s.kind == kind), -1)
        j = i + delta
        if i < 0 or not 0 <= j < len(steps):
            return
        steps[i], steps[j] = steps[j], steps[i]
        self._rebuild_organize(steps)
        self._autosave()

    def current_organize_steps(self) -> list[OrganizeStep]:
        steps: list[OrganizeStep] = []
        for _row, refs in self._org_rows:
            step = OrganizeStep(kind=refs.kind, enabled=refs.switch.isChecked())
            if refs.span is not None:
                step.date_span = _SPAN_KEYS[max(0, refs.span.current())]
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
        self.dg_switch.setAccessibleName("启用 DGHub 联动")
        enable_row.add(self.dg_switch)
        card.add_row(enable_row)

        self.dg_port_row = Row("本机数据端口", "与插件配置里的端点保持一致")
        self.dg_port = _spin(1, 65535, cfg.dghub.port or 8890, width=110)
        self.dg_port_row.add(self.dg_port)
        card.add_row(self.dg_port_row)

        # 关掉总开关时端口那一行整行降级。禁用原因由紧邻的父开关直接表达，
        # 不用再写一句说明。
        self.dg_switch.toggled.connect(self.dg_port_row.setEnabled)
        self.dg_switch.toggled.connect(self._autosave)
        self.dg_port_row.setEnabled(cfg.dghub.enabled)

        self._body.addWidget(card)
        self._note("开启后从游戏内存实时读取判定计数（只读，不修改游戏），在本机提供数据服务，"
                   "由 DGHub 里的「寸录 · 联动」插件读取并触发波形。"
                   "MISS / ATTACK / 结算的强度、波形预设、通道都在 DGHub 的插件配置页里调；"
                   "结算是否「寸了」按上面的判定规则算。")

    # ----------------------------- 自动截图 ---------------------------------
    def _build_capture(self) -> None:
        cfg = self._main.cfg
        self._section("自动截图")
        card = Card()

        enable_row = Row("启用自动截图")
        self.cap_switch = Switch()
        self.cap_switch.setChecked(cfg.capture.enabled)
        self.cap_switch.setAccessibleName("启用自动截图")
        enable_row.add(self.cap_switch)
        card.add_row(enable_row)

        self.cap_delay_row = Row("识别到结算画面后等待")
        self.cap_delay = QDoubleSpinBox()
        self.cap_delay.setRange(0.0, 15.0)
        self.cap_delay.setSingleStep(0.5)
        self.cap_delay.setDecimals(1)
        self.cap_delay.setSuffix(" 秒")
        self.cap_delay.setValue(cfg.capture.delay_s)
        self.cap_delay.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.cap_delay.setMinimumWidth(110)
        self.cap_delay_row.add(self.cap_delay)
        card.add_row(self.cap_delay_row)

        self.cap_switch.toggled.connect(self.cap_delay_row.setEnabled)
        self.cap_switch.toggled.connect(self._autosave)
        self.cap_delay_row.setEnabled(cfg.capture.enabled)

        self._body.addWidget(card)
        self._note("每首歌结算时自动截取游戏画面存进截图目录，判定数据直接取自内存，"
                   "新截图不再需要 OCR，原来的外部截图工具可以停用。等待时间是留给分数滚完的。"
                   "依赖游戏内存读取，本开关或上面的 DGHub 联动任一开启即生效。"
                   "历史截图重扫仍然走 OCR。")

    # ----------------------------- 外观 -------------------------------------
    def _build_appearance(self) -> None:
        self._section("外观")
        card = Card()
        row = Row("主题")
        self.appearance = Segmented([theme.APPEARANCE_LABELS[a] for a in theme.APPEARANCES])
        self.appearance.set_current(theme.APPEARANCES.index(self._main.cfg.appearance)
                                    if self._main.cfg.appearance in theme.APPEARANCES else 0)
        self.appearance.changed.connect(self._appearance_changed)
        row.add(self.appearance)
        card.add_row(row)
        self._body.addWidget(card)

    def _appearance_changed(self, index: int) -> None:
        self._main.cfg.appearance = theme.APPEARANCES[index]
        self._autosave()
        self._main.apply_appearance()

    # ----------------------------- 按钮 -------------------------------------
    def _build_actions(self) -> None:
        self._body.addSpacing(theme.GAP_SECTION)
        self._body.addWidget(widgets.note(
            "开关和选择改完立即生效并保存；目录、端口、秒数和得分区间要点「保存配置」。"))
        self._body.addSpacing(theme.GAP_CONTROL)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(theme.GAP_CONTROL)

        open_btn = QPushButton("打开输出文件夹")
        open_btn.clicked.connect(self._main.open_output)
        bar.addWidget(open_btn)
        bar.addStretch(1)

        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._main.save_config_from_ui)
        bar.addWidget(save_btn)

        # 整页只有这一个 Primary。它包含保存，所以「保存配置」保持 Secondary。
        self.rescan_btn = QPushButton("应用并重新扫描")
        self.rescan_btn.setProperty("role", "accent")
        self.rescan_btn.clicked.connect(self._main.apply_and_rescan)
        bar.addWidget(self.rescan_btn)

        holder = QWidget()
        holder.setObjectName("PageBody")
        holder.setLayout(bar)
        self._body.addWidget(holder)

    def set_scanning(self, scanning: bool) -> None:
        """扫描是异步的，按钮要进 Loading，否则连点会起好几个扫描线程。"""
        self.rescan_btn.setEnabled(not scanning)
        self.rescan_btn.setText("扫描中…" if scanning else "应用并重新扫描")

    # ----------------------------- 读回 -------------------------------------
    def read_instant_into(self, cfg: CunConfig) -> None:
        """开关、单选和选择器的当前状态。这些改完立即写盘。"""
        cfg.appearance = theme.APPEARANCES[max(0, self.appearance.current())]
        cfg.dghub.enabled = self.dg_switch.isChecked()
        cfg.capture.enabled = self.cap_switch.isChecked()

        steps = self.current_organize_steps()
        if steps:
            cfg.organize.steps = steps

        for cat in cfg.categories:
            refs = self._rules.get(cat.key)
            if refs is not None:
                cat.enabled = refs.switch.isChecked()

    def read_into(self, cfg: CunConfig) -> None:
        """界面上的全部状态，包括要明确提交的那些字段。"""
        self.read_instant_into(cfg)
        cfg.game_root = self.game_box.text().strip()
        cfg.screenshots_dir = self.shots_box.text().strip()
        cfg.output_root = self.out_box.text().strip()
        cfg.dghub.port = self.dg_port.value()
        cfg.capture.delay_s = self.cap_delay.value()

        for cat in cfg.categories:
            refs = self._rules.get(cat.key)
            if refs is None:
                continue
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


def _spin(minimum: int, maximum: int, value: int, width: int = 88) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    box.setGroupSeparatorShown(maximum > 1000)
    box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    box.setFixedWidth(width)
    box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return box
