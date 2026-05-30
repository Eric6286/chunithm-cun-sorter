# -*- coding: utf-8 -*-
"""
「今天你寸了吗」 — Fluent 2 GUI for the CHUNITHM 寸 watcher.

Features:
  * Mica background (Win11) + Fluent 2 widgets (qfluentwidgets).
  * Toggle each copy category and freely edit every numeric bound:
      AJ / SSS+寸 / SSS寸 / SS+寸 / SS寸 (by score) / A+M 判定寸.
  * Daily 寸-count line chart (QtCharts).
  * Background watcher with idle CPU priority; game detected by process polling
    (works with the unmodified start.bat). Closing the window keeps it watching
    in the system tray.
"""
import sys, os, winreg

from PySide6.QtCore import Qt, QTimer, QObject, Signal, QDateTime, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QIntValidator
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QFrame, QSystemTrayIcon)
from PySide6.QtCharts import (QChart, QChartView, QLineSeries, QValueAxis,
                              QDateTimeAxis)

from qfluentwidgets import (FluentWindow, NavigationItemPosition, SwitchButton,
                            SpinBox, PushButton, PrimaryPushButton, BodyLabel,
                            TitleLabel, SubtitleLabel, StrongBodyLabel, CardWidget,
                            CaptionLabel, ComboBox, TextEdit, setTheme, Theme,
                            FluentIcon, InfoBar, InfoBarPosition, CheckBox,
                            LargeTitleLabel, themeColor, isDarkTheme, LineEdit)

import cun_detect
import cun_core

APP_NAME = "今天你寸了吗"
HERE = cun_detect.data_dir()
ICON_PATH = os.path.join(HERE, "icon.ico")


def app_icon():
    from PySide6.QtGui import QIcon
    if os.path.exists(ICON_PATH):
        return QIcon(ICON_PATH)
    return FluentIcon.HEART.icon()


# --------------------- thread -> GUI signal bridge --------------------------
class Bridge(QObject):
    matched = Signal(str, dict, list)
    status = Signal(str)
    scan_done = Signal(dict)


# ----------------------------- config page ----------------------------------
class ConfigInterface(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setObjectName("configInterface")
        self.rows = {}            # key -> dict of widgets
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 18, 28, 18)
        root.setSpacing(12)

        root.addWidget(TitleLabel("规则设置"))

        for cat in self.main.cfg.get("categories", []):
            root.addWidget(self._build_card(cat))

        root.addStretch(1)
        btns = QHBoxLayout()
        save = PushButton("保存配置", self, FluentIcon.SAVE)
        save.clicked.connect(self.main.save_config_from_ui)
        rescan = PrimaryPushButton("应用并重新扫描", self, FluentIcon.SYNC)
        rescan.clicked.connect(self.main.apply_and_rescan)
        openf = PushButton("打开输出文件夹", self, FluentIcon.FOLDER)
        openf.clicked.connect(self.main.open_output)
        btns.addWidget(save); btns.addWidget(rescan); btns.addWidget(openf); btns.addStretch(1)
        root.addLayout(btns)

    def _num(self, value, hi=1010000, width=120):
        """A clean Fluent text field for integer input (no spin arrows)."""
        e = LineEdit(self)
        e.setValidator(QIntValidator(0, int(hi), self))
        e.setText(str(int(value)))
        e.setFixedWidth(width)
        e.setClearButtonEnabled(False)
        e.setAlignment(Qt.AlignCenter)
        return e

    @staticmethod
    def _ival(widget, default):
        try:
            return int(widget.text())
        except (ValueError, TypeError):
            return default

    def _ranks(self):
        th = self.main.cfg.get("rank_thresholds", {})
        return [k for k, _ in sorted(th.items(), key=lambda kv: kv[1], reverse=True)]

    def _build_card(self, cat):
        card = CardWidget(self)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)

        sw = SwitchButton(self)
        sw.setChecked(bool(cat.get("enabled")))
        lay.addWidget(sw)

        col = QVBoxLayout(); col.setSpacing(2)
        col.addWidget(StrongBodyLabel(cat.get("label", cat["key"])))
        col.addWidget(CaptionLabel("→ %s" % cat.get("folder", "")))
        lay.addLayout(col)
        lay.addStretch(1)

        refs = {"switch": sw}
        kind = cat.get("kind")
        if kind == "score":
            lo = self._num(cat.get("lo", 0), hi=cat.get("hi", 1010000), width=128)
            lay.addWidget(BodyLabel("得分"))
            lay.addWidget(lo)
            lay.addWidget(BodyLabel("~ %s" % format(cat.get("hi", 0), ",")))
            refs["lo"] = lo
        elif kind == "ajcun":
            mhi = self._num(cat.get("m_hi", 4), hi=100, width=64)
            lay.addWidget(BodyLabel("0 < MISS ≤"))
            lay.addWidget(mhi)
            refs["m_hi"] = mhi
        elif kind == "am":
            ahi = self._num(cat.get("a_hi", 4), hi=100, width=64)
            mhi = self._num(cat.get("m_hi", 4), hi=100, width=64)
            rank = ComboBox(self)
            rank.addItems(self._ranks())
            cur = cat.get("min_rank", "SSS")
            if cur in self._ranks():
                rank.setCurrentText(cur)
            rank.setFixedWidth(120)
            lay.addWidget(BodyLabel("ATTACK ≤"))
            lay.addWidget(ahi)
            lay.addWidget(BodyLabel("MISS ≤"))
            lay.addWidget(mhi)
            lay.addWidget(BodyLabel("且评级 ≥"))
            lay.addWidget(rank)
            refs["a_hi"], refs["m_hi"], refs["rank"] = ahi, mhi, rank
        # kinds "aj" and "fc" have only the on/off switch (no extra controls)
        self.rows[cat["key"]] = refs
        return card

    def read_into(self, cfg):
        for cat in cfg.get("categories", []):
            r = self.rows.get(cat["key"])
            if not r:
                continue
            cat["enabled"] = r["switch"].isChecked()
            if cat.get("kind") == "score":
                cat["lo"] = self._ival(r["lo"], cat.get("lo", 0))   # upper (hi) stays fixed
            elif cat.get("kind") == "ajcun":
                cat["m_hi"] = self._ival(r["m_hi"], cat.get("m_hi", 4))
            elif cat.get("kind") == "am":
                cat["a_hi"] = self._ival(r["a_hi"], cat.get("a_hi", 4))
                cat["m_hi"] = self._ival(r["m_hi"], cat.get("m_hi", 4))
                cat["min_rank"] = r["rank"].currentText()
                for k in ("am_lo", "am_hi", "score_min"):
                    cat.pop(k, None)


# ----------------------------- stats page ----------------------------------
class StatsInterface(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setObjectName("statsInterface")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 18, 28, 18)
        root.setSpacing(14)

        head = QHBoxLayout()
        col = QVBoxLayout(); col.setSpacing(2)
        col.addWidget(TitleLabel("每日「寸」统计"))
        self.range_lbl = CaptionLabel("—")
        col.addWidget(self.range_lbl)
        head.addLayout(col)
        head.addStretch(1)
        refresh = PushButton("刷新", self, FluentIcon.SYNC)
        refresh.clicked.connect(self.refresh)
        head.addWidget(refresh)
        root.addLayout(head)

        cards = QHBoxLayout(); cards.setSpacing(14)
        self.c_today, self.v_today = self._stat_card("今天")
        self.c_week, self.v_week = self._stat_card("近 7 天")
        self.c_total, self.v_total = self._stat_card("累计")
        self.c_best, self.v_best = self._stat_card("最高一天")
        for c in (self.c_today, self.c_week, self.c_total, self.c_best):
            cards.addWidget(c, 1)
        root.addLayout(cards)

        chart_card = CardWidget(self)
        cl = QVBoxLayout(chart_card); cl.setContentsMargins(10, 10, 10, 6)
        self.chart = QChart()
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(6, 6, 6, 6))
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignBottom)
        self.view = QChartView(self.chart)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setStyleSheet("background: transparent")
        self.view.setMinimumHeight(380)
        cl.addWidget(self.view)
        root.addWidget(chart_card, 1)

    def _stat_card(self, title):
        card = CardWidget(self)
        v = QVBoxLayout(card); v.setContentsMargins(20, 16, 20, 16); v.setSpacing(0)
        val = LargeTitleLabel("0")
        cap = CaptionLabel(title)
        v.addWidget(val); v.addWidget(cap)
        card._cap = cap
        return card, val

    def refresh(self):
        cfg = cun_detect.load_config()
        data = cun_core.daily_counts(cfg)
        fg = QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)
        grid = QColor(255, 255, 255, 36) if isDarkTheme() else QColor(0, 0, 0, 28)
        accent = themeColor()
        aj_color = QColor(255, 180, 70)

        self.chart.removeAllSeries()
        for ax in list(self.chart.axes()):
            self.chart.removeAxis(ax)

        cun_s = QLineSeries(); cun_s.setName("寸")
        aj_s = QLineSeries(); aj_s.setName("AJ")
        ymax = 1
        for date, c, a in data:
            x = float(QDateTime.fromString(date, "yyyy-MM-dd").toMSecsSinceEpoch())
            cun_s.append(x, c); aj_s.append(x, a)
            ymax = max(ymax, c, a)

        pen = QPen(accent); pen.setWidth(3); pen.setCosmetic(True)
        cun_s.setPen(pen); cun_s.setPointsVisible(True)
        cun_s.setPointLabelsVisible(True); cun_s.setPointLabelsFormat("@yPoint")
        cun_s.setPointLabelsColor(fg); cun_s.setPointLabelsClipping(False)
        ajp = QPen(aj_color); ajp.setWidth(2); ajp.setStyle(Qt.DashLine)
        aj_s.setPen(ajp); aj_s.setPointsVisible(True)

        self.chart.addSeries(cun_s); self.chart.addSeries(aj_s)

        axx = QDateTimeAxis(); axx.setFormat("M/d"); axx.setTitleText("日期")
        axx.setTickCount(min(8, max(2, len(data) or 2)))
        axy = QValueAxis(); axy.setRange(0, ymax + 1); axy.setLabelFormat("%d")
        axy.setTickInterval(1); axy.setTitleText("个数")
        for ax in (axx, axy):
            ax.setLabelsColor(fg); ax.setTitleBrush(fg)
            ax.setGridLineColor(grid); ax.setLinePenColor(grid)
        self.chart.addAxis(axx, Qt.AlignBottom); self.chart.addAxis(axy, Qt.AlignLeft)
        for s in (cun_s, aj_s):
            s.attachAxis(axx); s.attachAxis(axy)
        self.chart.legend().setLabelColor(fg)

        # summary numbers
        now = QDateTime.currentDateTime()
        today = now.toString("yyyy-MM-dd")
        tc = next((c for d, c, a in data if d == today), 0)
        total = sum(c for _, c, _ in data)
        week_days = set(now.addDays(-i).toString("yyyy-MM-dd") for i in range(7))
        week = sum(c for d, c, _ in data if d in week_days)
        best = max(data, key=lambda t: t[1]) if data else None
        self.v_today.setText(str(tc))
        self.v_week.setText(str(week))
        self.v_total.setText(str(total))
        if best and best[1] > 0:
            self.v_best.setText(str(best[1]))
            self.c_best._cap.setText("最高一天 · " + best[0][5:])
        else:
            self.v_best.setText("0"); self.c_best._cap.setText("最高一天")
        if data:
            self.range_lbl.setText("统计区间 %s ~ %s    ·    更新于 %s"
                                   % (data[0][0], data[-1][0], now.toString("HH:mm:ss")))
        else:
            self.range_lbl.setText("暂无数据    ·    更新于 " + now.toString("HH:mm:ss"))


# ----------------------------- run page -------------------------------------
class RunInterface(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setObjectName("runInterface")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 18, 28, 18)
        root.setSpacing(12)
        root.addWidget(TitleLabel("运行 / 监视"))

        mode_card = CardWidget(self); ml = QHBoxLayout(mode_card)
        ml.setContentsMargins(18, 12, 18, 12)
        ml.addWidget(StrongBodyLabel("处理模式")); ml.addStretch(1)
        self.mode = ComboBox(self)
        self.mode.addItems(["realtime (实时·低优先级)", "on_close (关游戏后处理)"])
        self.mode.setCurrentIndex(0 if self.main.cfg.get("process_mode") == "realtime" else 1)
        self.mode.currentIndexChanged.connect(self.main.on_mode_changed)
        self.mode.setFixedWidth(240)
        ml.addWidget(self.mode)
        root.addWidget(mode_card)

        st_card = CardWidget(self); sl = QHBoxLayout(st_card)
        sl.setContentsMargins(18, 12, 18, 12)
        self.start_btn = PrimaryPushButton("启动监视", self, FluentIcon.PLAY)
        self.start_btn.clicked.connect(self.main.toggle_watch)
        self.game_lbl = BodyLabel("游戏: 检测中…")
        self.watch_lbl = BodyLabel("监视: 未启动")
        sl.addWidget(self.start_btn); sl.addSpacing(16)
        sl.addWidget(self.watch_lbl); sl.addSpacing(16); sl.addWidget(self.game_lbl); sl.addStretch(1)
        root.addWidget(st_card)

        self.autostart = CheckBox("开机自启「今天你寸了吗」", self)
        self.autostart.setChecked(self.main.is_autostart())
        self.autostart.stateChanged.connect(self.main.set_autostart)
        root.addWidget(self.autostart)

        root.addWidget(StrongBodyLabel("最近命中"))
        self.logbox = TextEdit(self); self.logbox.setReadOnly(True)
        root.addWidget(self.logbox, 1)


# ----------------------------- main window ----------------------------------
class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.cfg = cun_detect.load_config()
        self.watcher = None
        self.bridge = Bridge()
        self.bridge.matched.connect(self.on_match)
        self.bridge.status.connect(self.on_status)
        self.bridge.scan_done.connect(self.on_scan_done)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1040, 720)
        try:
            self.setMicaEffectEnabled(True)
        except Exception:
            pass

        self.configInterface = ConfigInterface(self)
        self.statsInterface = StatsInterface(self)
        self.runInterface = RunInterface(self)
        self.addSubInterface(self.configInterface, FluentIcon.SETTING, "配置")
        self.addSubInterface(self.statsInterface, FluentIcon.MARKET, "统计")
        self.addSubInterface(self.runInterface, FluentIcon.PLAY, "运行")

        self._init_tray()
        self.statsInterface.refresh()

        # poll game status for the indicator
        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self._update_game_label)
        self.game_timer.start(4000)
        self._update_game_label()

    # ---- tray ----
    def _init_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        from qfluentwidgets import SystemTrayMenu, Action
        menu = SystemTrayMenu(parent=self)
        menu.addAction(Action(FluentIcon.HOME, "显示主界面", triggered=self._show_normal))
        menu.addAction(Action(FluentIcon.CLOSE, "退出", triggered=self._quit))
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self._show_normal() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def _show_normal(self):
        self.show(); self.raise_(); self.activateWindow()

    def _quit(self):
        if self.watcher:
            self.watcher.stop()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e):
        # keep watching in tray instead of quitting
        if self.watcher and self.watcher.is_alive():
            e.ignore(); self.hide()
            self.tray.showMessage(APP_NAME, "已最小化到托盘，继续后台监视。", FluentIcon.HEART.icon(), 3000)
        else:
            self._quit(); e.accept()

    # ---- config ----
    def save_config_from_ui(self):
        self.configInterface.read_into(self.cfg)
        cun_detect.save_config(self.cfg)
        InfoBar.success("已保存", "配置已写入 cun_config.json", duration=2500,
                        position=InfoBarPosition.TOP, parent=self)

    def apply_and_rescan(self):
        import threading
        self.save_config_from_ui()
        InfoBar.info("正在重新扫描…", "按当前规则重建输出文件夹（不阻塞界面）", duration=2500,
                     position=InfoBarPosition.TOP, parent=self)

        def work():
            try:
                r = cun_core.scan_all(cun_detect.load_config(), rebuild=True)
            except Exception as e:
                r = {"total": 0, "cun": 0, "aj": 0, "error": str(e)}
            self.bridge.scan_done.emit(r)

        threading.Thread(target=work, daemon=True).start()

    def on_scan_done(self, r):
        self.statsInterface.refresh()
        if r.get("error"):
            InfoBar.error("扫描出错", r["error"], duration=6000,
                          position=InfoBarPosition.TOP, parent=self)
        else:
            InfoBar.success("扫描完成", "寸=%d  AJ=%d (共 %d 张)" % (r["cun"], r["aj"], r["total"]),
                            duration=4000, position=InfoBarPosition.TOP, parent=self)

    def open_output(self):
        os.startfile(self.cfg["output_root"])

    def on_mode_changed(self, idx):
        self.cfg["process_mode"] = "realtime" if idx == 0 else "on_close"
        cun_detect.save_config(self.cfg)

    # ---- watcher ----
    def toggle_watch(self):
        if self.watcher and self.watcher.is_alive():
            self.watcher.stop()
            self.watcher = None
            self.runInterface.start_btn.setText("启动监视")
            self.runInterface.watch_lbl.setText("监视: 已停止")
        else:
            self.watcher = cun_core.Watcher(
                get_cfg=lambda: cun_detect.load_config(),
                on_match=lambda f, rec, m: self.bridge.matched.emit(f, rec, [c["key"] for c in m]),
                on_status=lambda s: self.bridge.status.emit(s))
            self.watcher.start()
            self.runInterface.start_btn.setText("停止监视")
            self.runInterface.watch_lbl.setText("监视: 运行中")

    def on_match(self, fname, rec, keys):
        self.runInterface.logbox.append("✓ %s  得分=%s A=%s M=%s  [%s]"
                                        % (fname, rec.get("score"), rec.get("attack"),
                                           rec.get("miss"), "+".join(keys)))
        self.statsInterface.refresh()

    def on_status(self, msg):
        self.runInterface.watch_lbl.setText("监视: " + msg)

    def _update_game_label(self):
        running = cun_core.is_process_running(self.cfg.get("game_process", "chusanApp.exe"))
        self.runInterface.game_lbl.setText("游戏: " + ("运行中 ●" if running else "未运行 ○"))

    # ---- autostart ----
    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _autostart_cmd(self):
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pyw):
            pyw = sys.executable
        return '"%s" "%s"' % (pyw, os.path.join(HERE, "cun_gui.py"))

    def is_autostart(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._RUN_KEY) as k:
                winreg.QueryValueEx(k, APP_NAME)
                return True
        except OSError:
            return False

    def set_autostart(self, state):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                if self.autostart.isChecked():
                    winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, self._autostart_cmd())
                else:
                    try:
                        winreg.DeleteValue(k, APP_NAME)
                    except OSError:
                        pass
        except Exception:
            pass


def main():
    # make Windows treat us as our own app (taskbar name/icon, not "Python")
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JinTianNiCunLeMa.App")
    except Exception:
        pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())
    setTheme(Theme.AUTO)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
