# -*- coding: utf-8 -*-
"""
Headless persistent watcher (no GUI). Detects the game by polling the process
list, so the game can be launched normally with start.bat. Only screenshots that
appear after this starts are auto-processed (use scan_all.py for the backlog).

Usually you'll run the GUI app instead (cun_gui.py); this is for a no-window setup.
"""
import sys, time
import cun_detect
import cun_core


def main():
    w = cun_core.Watcher(get_cfg=lambda: cun_detect.load_config())
    w.start()
    try:
        while w.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        w.stop()
        w.join(timeout=5)


if __name__ == "__main__":
    main()
