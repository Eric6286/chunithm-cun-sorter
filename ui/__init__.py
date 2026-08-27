# -*- coding: utf-8 -*-
"""界面层（PySide6）。

**这个包不做急切导入。** 在这里 ``from .main_window import MainWindow`` 会让
``import ui.theme`` 这种轻量用途也把整套窗口拉起来，命令行入口和测试就跑不了了。
要哪个模块就 ``import ui.xxx``。
"""
