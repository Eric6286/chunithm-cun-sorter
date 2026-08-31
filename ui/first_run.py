# -*- coding: utf-8 -*-
"""首次运行向导：把 CHUNITHM 装在哪这件事问清楚。

安装器里已经选过的话不会走到这儿（那份选择通过 ``install.ini`` 进了配置）。
便携解压、或者安装时跳过了这一步的用户才会看到。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QPushButton, QVBoxLayout, QWidget)

from core import game_locator
from core.config import derive_paths, normalize_game_root
from core.models import CunConfig

from . import theme, widgets
from .widgets import FocusRing, Row


class FirstRunDialog(QDialog):
    """选完之后用 :attr:`game_root` 取结果；用户跳过则为 ``None``。"""

    def __init__(self, cfg: CunConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择 CHUNITHM 游戏目录")
        self.setMinimumWidth(560)
        self.game_root: Path | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PADDING_PAGE_X, theme.PADDING_PAGE_Y,
                                 theme.PADDING_PAGE_X, theme.PADDING_PAGE_Y)
        outer.setSpacing(0)

        outer.addWidget(widgets.title("CHUNITHM 装在哪？"))
        outer.addSpacing(theme.GAP_RELATED)
        outer.addWidget(widgets.note(
            "本程序要知道游戏目录才能找到截图文件夹和 start.bat。"
            "选中 CHUNITHM 的根目录（里面有 bin 文件夹）就行。"))

        # 对话框本身已经是一层独立的浮层，里面再包一张卡片就是重复包裹。
        # 两行直接摆在对话框上，中间一条分隔线。
        outer.addSpacing(theme.GAP_GROUP)
        self._path_row = Row("游戏目录", "尚未选择", inset=False)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        self._path_row.add(browse)
        outer.addWidget(self._path_row)

        line = QFrame()
        line.setObjectName("Separator")
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedHeight(1)
        outer.addWidget(line)

        self._derived_row = Row("截图目录", "—", inset=False)
        outer.addWidget(self._derived_row)

        outer.addSpacing(theme.GAP_GROUP)
        self._hint = widgets.note("")
        outer.addWidget(self._hint)

        outer.addSpacing(theme.GAP_SECTION)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(theme.GAP_CONTROL)
        skip = QPushButton("以后再说")
        skip.setProperty("role", "quiet")
        skip.clicked.connect(self.reject)
        buttons.addWidget(skip)
        buttons.addStretch(1)
        self._confirm = QPushButton("就用这个目录")
        self._confirm.setProperty("role", "accent")
        self._confirm.setEnabled(False)
        self._confirm.clicked.connect(self.accept)
        buttons.addWidget(self._confirm)
        outer.addLayout(buttons)

        # 对话框是独立的顶层窗口，焦点环要自己装一个
        self._focus_ring = FocusRing(self)

        detected = game_locator.autodetect(cfg)
        if detected is not None:
            self._set_root(detected, "自动找到的，不对就点「浏览…」换一个。")
        else:
            self._set_hint("没自动找到，点「浏览…」选一下。"
                           "跳过的话之后也能在「配置」页里补。")

    def _set_hint(self, text: str) -> None:
        self._hint.setText(theme.rich_text(text, theme.SECONDARY))

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "选择 CHUNITHM 游戏目录",
            self._path_row.sublabel.text() if self._path_row.sublabel else "")
        if not chosen:
            return
        root = normalize_game_root(chosen)
        if root is None:
            self._set_hint("这个目录不像 CHUNITHM 的安装位置：里面应该有一个 bin 文件夹。"
                           "选根目录或者它的 bin 目录都行。")
            return
        self._set_root(root, "")

    def _set_root(self, root: Path, hint: str) -> None:
        self.game_root = root
        self._path_row.set_sublabel(str(root))
        shots, bat = derive_paths(root)
        detail = shots if Path(shots).is_dir() else f"{shots}（还不存在，会自动创建）"
        if bat:
            detail += f" · start.bat：{bat}"
        self._derived_row.set_sublabel(detail)
        self._confirm.setEnabled(True)
        self._confirm.setDefault(True)
        self._set_hint(hint)


def ask_for_game_root(cfg: CunConfig, parent: QWidget | None = None) -> Path | None:
    """弹一次向导。用户跳过返回 ``None``。"""
    dialog = FirstRunDialog(cfg, parent)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    if dialog.exec() and dialog.game_root is not None:
        return dialog.game_root
    return None
