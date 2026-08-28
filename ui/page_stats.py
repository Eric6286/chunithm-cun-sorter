# -*- coding: utf-8 -*-
"""「统计」页：四块汇总数字 + 每日 寸 / AJ / FC 曲线。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from core import classifier
from core import config as config_mod

from . import theme, widgets
from .widgets import DailyChart, StatTile

if TYPE_CHECKING:
    from .main_window import MainWindow


class StatsPage(QWidget):
    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        self._data: list[tuple[str, int, int, int]] = []

        outer = widgets.page_shell(self)
        outer.setSpacing(theme.GRID * 2)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(widgets.page_title("统计"))
        # 用会换行的 caption 会在这儿折成两行：它在 QHBoxLayout 里只拿得到自己的
        # sizeHint 那么宽，哪怕右边还空着一大片
        self.range_label = widgets.ElidedLabel("—")
        title_col.addWidget(self.range_label)
        header.addLayout(title_col, 1)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        outer.addLayout(header)

        tiles = QGridLayout()
        tiles.setSpacing(theme.GRID * 1.5)
        self.today = StatTile("今天")
        self.week = StatTile("近 7 天")
        self.total = StatTile("累计")
        self.best = StatTile("最高一天")
        for col, tile in enumerate((self.today, self.week, self.total, self.best)):
            tiles.addWidget(tile, 0, col)
            tiles.setColumnStretch(col, 1)
        outer.addLayout(tiles)

        chart_card = QFrame()
        chart_card.setObjectName("Card")
        chart_box = QVBoxLayout(chart_card)
        chart_box.setContentsMargins(theme.GRID * 2, theme.GRID * 2,
                                     theme.GRID * 2, theme.GRID * 2)
        self.chart = DailyChart()
        chart_box.addWidget(self.chart)
        outer.addWidget(chart_card, 1)

    def refresh(self) -> None:
        cfg = config_mod.load_cached()
        self._data = classifier.daily_counts(cfg)
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        by_date = {d: (cun, aj, fc) for d, cun, aj, fc in self._data}
        week_days = {(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)}

        self.today.set_value(by_date.get(today, (0, 0, 0))[0])
        self.week.set_value(sum(v[0] for d, v in by_date.items() if d in week_days))
        self.total.set_value(sum(v[0] for v in by_date.values()))

        best = max(self._data, key=lambda d: d[1], default=None)
        if best is not None and best[1] > 0:
            self.best.set_value(best[1])
            self.best.set_caption("最高一天 · " + best[0][5:])
        else:
            self.best.set_value(0)
            self.best.set_caption("最高一天")

        if self._data:
            self.range_label.setText(
                f"统计区间 {self._data[0][0]} ~ {self._data[-1][0]}    ·    "
                f"更新于 {now:%H:%M:%S}")
        else:
            self.range_label.setText(f"暂无数据    ·    更新于 {now:%H:%M:%S}")

        self.chart.set_data(self._data)
