# -*- coding: utf-8 -*-
"""
One-shot backlog scanner. Classifies every screenshot and copies AJ / 寸 results
into their folders. OCR results are cached, so re-runs are fast.

Usage:
    python scan_all.py            # classify (OCR new files), copy matches
    python scan_all.py --rebuild  # clear tool-created files in output folders first, then recopy
    python scan_all.py --reocr    # ignore the OCR cache and re-read every screenshot
"""
import sys
import cun_detect
import cun_core


def main(argv):
    cfg = cun_detect.load_config()
    rebuild = "--rebuild" in argv
    reocr = "--reocr" in argv or "--force" in argv

    def prog(i, n, c, a):
        print("  ...%d/%d processed  (CUN=%d  AJ=%d)" % (i, n, c, a))

    print("Scanning %s ..." % cfg["screenshots_dir"])
    if rebuild:
        print("(rebuild: clearing previously copied files first)")
    r = cun_core.scan_all(cfg, progress=prog, rebuild=rebuild, reocr=reocr)
    print("\nDone. total=%d  CUN=%d  AJ=%d" % (r["total"], r["cun"], r["aj"]))
    print("Output root: %s" % cfg["output_root"])


if __name__ == "__main__":
    main(sys.argv[1:])
