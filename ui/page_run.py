# -*- coding: utf-8 -*-
"""「运行」页：处理模式、启停监视、各路状态、自启动、最近命中。

这一页的开关全部立即生效（自启动和 start.bat 本来就是即时动作），
与「配置」页的保存边界一致。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QPlainTextEdit, QPushButton, QWidget

from core import autostart, start_bat
from core import config as config_mod

from . import theme, widgets
from .widgets import Card, Combo, Row, Switch, Toast

if TYPE_CHECKING:
    from .main_window import MainWindow

_MODES = (("realtime", "实时处理（低优先级）"), ("on_close", "关掉游戏之后再处理"))
#: 最近命中最多留这么多行，跑一整天也不会把内存吃光
_LOG_LIMIT = 500


class RunPage(QWidget):
    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        self._initializing = True

        outer = widgets.page_shell(self)
        outer.addWidget(widgets.page_title("运行"))
        outer.addSpacing(theme.PAGE_TITLE_TO_SECTION)

        # --- 监视 ---
        outer.addWidget(widgets.section_title("监视"))
        outer.addSpacing(theme.SECTION_TITLE_TO_CARD)
        watch_card = Card()

        mode_row = Row("处理模式")
        # 两个选项，标签都不短 → Picker 而不是 Segmented
        self.mode_box = Combo()
        for _, label in _MODES:
            self.mode_box.addItem(label)
        self.mode_box.setCurrentIndex(
            0 if self._main.cfg.process_mode == "realtime" else 1)
        self.mode_box.currentIndexChanged.connect(self._mode_changed)
        self.mode_box.setMinimumWidth(210)
        mode_row.add(self.mode_box)
        watch_card.add_row(mode_row)

        state_row = Row("监视状态", "未启动")
        self.watch_label = state_row
        self.start_button = QPushButton("启动监视")
        self.start_button.setProperty("role", "accent")
        self.start_button.clicked.connect(self._main.toggle_watch)
        state_row.add(self.start_button)
        watch_card.add_row(state_row)

        game_row = Row("游戏", "检测中…")
        self.game_row = game_row
        watch_card.add_row(game_row)
        outer.addWidget(watch_card)
        outer.addSpacing(theme.CARD_TO_NOTE)
        outer.addWidget(widgets.note(
            "监视运行时关掉窗口等于最小化到托盘继续后台监视。"
            "右键托盘图标可以重新显示或退出。"))

        # --- 联动 ---
        outer.addSpacing(theme.GAP_SECTION)
        outer.addWidget(widgets.section_title("DGHub 联动"))
        outer.addSpacing(theme.SECTION_TITLE_TO_CARD)
        link_card = Card()
        self.link_row = Row("数据服务", "未启用")
        link_card.add_row(self.link_row)
        self.judge_row = Row("判定读取", "未启用")
        link_card.add_row(self.judge_row)
        outer.addWidget(link_card)
        outer.addSpacing(theme.CARD_TO_NOTE)
        outer.addWidget(widgets.note("开关在「配置」页，这里只显示当前状态。"))

        # --- 自启动 ---
        outer.addSpacing(theme.GAP_SECTION)
        outer.addWidget(widgets.section_title("自启动"))
        outer.addSpacing(theme.SECTION_TITLE_TO_CARD)
        auto_card = Card()

        login_row = Row("开机时启动本程序")
        self.autostart_switch = Switch()
        self.autostart_switch.setChecked(autostart.is_enabled())
        self.autostart_switch.setAccessibleName("开机时启动本程序")
        self.autostart_switch.toggled.connect(autostart.set_enabled)
        login_row.add(self.autostart_switch)
        auto_card.add_row(login_row)

        self.bat_row = Row("接入 start.bat", "")
        self.bat_switch = Switch()
        self.bat_switch.setAccessibleName("接入 start.bat")
        self.bat_switch.toggled.connect(self._toggle_start_bat)
        self.bat_row.add(self.bat_switch)
        auto_card.add_row(self.bat_row)

        outer.addWidget(auto_card)
        outer.addSpacing(theme.CARD_TO_NOTE)
        outer.addWidget(widgets.note(
            "接入 start.bat 之后，启动游戏会顺带拉起本程序并开始监视、直接缩到托盘。"
            "原文件会先备份成 .cun-backup，关掉开关可以精确还原。"))

        # --- 最近命中 ---
        outer.addSpacing(theme.GAP_SECTION)
        outer.addWidget(widgets.section_title("最近命中"))
        outer.addSpacing(theme.SECTION_TITLE_TO_CARD)
        # 日志属于「需要快速纵向扫描的高密度内容」，不包 Card；
        # 用 Sunken 表达它是一块内嵌的 Console。
        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("LogBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(_LOG_LIMIT)
        self.log_box.setFont(theme.font(theme.MONO, mono=True))
        self.log_box.setPlaceholderText("监视启动后，命中的截图会一条条记在这里")
        self.log_box.setMinimumHeight(theme.SPACE_10 * 4)
        outer.addWidget(self.log_box, 1)

        self.refresh_start_bat()
        self._initializing = False

    # ----------------------------- 交互 -------------------------------------
    def _mode_changed(self, index: int) -> None:
        if self._initializing:
            return
        self._main.on_mode_changed(_MODES[index][0])

    def _toggle_start_bat(self, checked: bool) -> None:
        if self._initializing:
            return
        cfg = self._main.cfg
        if checked:
            bat = cfg.start_bat
            if not bat or not Path(bat).is_file():
                bat = self._main.pick_file("选择游戏的 start.bat", "批处理 (*.bat *.cmd)")
                if not bat:
                    self.refresh_start_bat()
                    return
            try:
                start_bat.hook(bat)
                cfg.start_bat = bat
                config_mod.save(cfg)
                self._main.show_toast(
                    "已接入",
                    f"已在 {Path(bat).name} 中加入自启动行，原文件备份为 .cun-backup",
                    Toast.SUCCESS)
            except OSError as e:
                self._main.show_toast("接入失败", str(e), Toast.ERROR)
        else:
            try:
                if cfg.start_bat:
                    start_bat.unhook(cfg.start_bat)
            except OSError as e:
                self._main.show_toast("移除失败", str(e), Toast.ERROR)
        self.refresh_start_bat()

    def refresh_start_bat(self) -> None:
        bat = self._main.cfg.start_bat
        hooked = bool(bat) and start_bat.is_hooked(bat)
        was = self._initializing
        self._initializing = True                   # 别让程序化的置位触发 toggled
        self.bat_switch.setChecked(hooked)
        self._initializing = was
        if hooked:
            self.bat_row.set_sublabel(bat)
        elif bat:
            self.bat_row.set_sublabel(f"{bat}（未接入）")
        else:
            self.bat_row.set_sublabel("尚未选择游戏的 start.bat")

    # ----------------------------- 主窗口回调 -------------------------------
    def set_watch_state(self, running: bool, text: str) -> None:
        self.start_button.setText("停止监视" if running else "启动监视")
        self.watch_label.set_sublabel(text)

    def set_watch_text(self, text: str) -> None:
        self.watch_label.set_sublabel(text)

    def set_game_text(self, text: str) -> None:
        self.game_row.set_sublabel(text)

    def set_link_text(self, text: str) -> None:
        self.link_row.set_sublabel(text)

    def set_judge_text(self, text: str) -> None:
        self.judge_row.set_sublabel(text)

    def append_log(self, line: str) -> None:
        self.log_box.appendPlainText(line)

    def retheme(self) -> None:
        """切换深浅之后，自绘和用代码设过的字体要重新取一遍。"""
        self.log_box.setFont(theme.font(theme.MONO, mono=True))
