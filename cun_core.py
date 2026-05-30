# -*- coding: utf-8 -*-
"""
Classification + processing + watcher for the CHUNITHM 寸 tool.

Categories (configured in cun_config.json, all bounds editable in the GUI):
  - AJ    : ATTACK==0 and MISS==0  (All Justice; NOT a 寸 -> its own folder)
  - score : lo <= SCORE <= hi       ("just missed rank X": SSS+/SSS/SS+/SS 寸)
  - am    : am_lo < ATTACK+MISS <= am_hi  AND  SCORE >= score_min  (differ-by-a-bit 寸)

OCR results are cached in cun_ocr_cache.json so re-classifying with new bounds is
instant (no re-OCR). Game state is detected by polling the process list, so the
game can still be launched with the unmodified start.bat.
"""
import os, re, sys, json, time, shutil, ctypes, threading
from ctypes import wintypes

import cun_detect

HERE = cun_detect.data_dir()
CACHE_PATH = os.path.join(HERE, "cun_ocr_cache.json")
LOG_PATH = os.path.join(HERE, "cun.log")

POLL_SEC = 2.0
SETTLE_SEC = 1.0
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


# ----------------------------- small utils ----------------------------------
def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    return line


def list_pngs(d):
    try:
        return [f for f in os.listdir(d) if f.lower().endswith(".png")]
    except Exception:
        return []


def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache):
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, CACHE_PATH)


def set_idle_priority():
    IDLE_PRIORITY_CLASS = 0x00000040
    try:
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), IDLE_PRIORITY_CLASS)
        return True
    except Exception:
        return False


def is_process_running(name):
    TH32CS_SNAPPROCESS = 0x00000002

    class PE32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_char * 260),
        ]

    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return False
    try:
        e = PE32(); e.dwSize = ctypes.sizeof(PE32)
        target = name.lower().encode("ascii", "ignore")
        if k.Process32First(snap, ctypes.byref(e)):
            while True:
                if e.szExeFile.lower() == target:
                    return True
                if not k.Process32Next(snap, ctypes.byref(e)):
                    break
        return False
    finally:
        k.CloseHandle(snap)


# ----------------------------- OCR + classify --------------------------------
def get_ocr(path, cfg, cache):
    """Return cached OCR for a file, running detection on first sight."""
    fn = os.path.basename(path)
    rec = cache.get(fn)
    if rec is not None:
        return rec
    r = cun_detect.detect(path, cfg)
    rec = {"score": r["score"], "attack": r["attack"], "miss": r["miss"]}
    cache[fn] = rec
    return rec


def classify(rec, cfg):
    """Return the list of enabled category dicts that this result matches."""
    s, a, m = rec.get("score"), rec.get("attack"), rec.get("miss")
    out = []
    for cat in cfg.get("categories", []):
        if not cat.get("enabled"):
            continue
        kind = cat.get("kind")
        if kind == "aj":                                 # All Justice
            if a == 0 and m == 0:
                out.append(cat)
        elif kind == "fc":                               # Full Combo: A!=0, M=0
            if a is not None and m is not None and a != 0 and m == 0:
                out.append(cat)
        elif kind == "ajcun":                            # 差点 AJ: A=0, 0<M<=x
            if a == 0 and m is not None and 0 < m <= cat.get("m_hi", 4):
                out.append(cat)
        elif kind == "score":
            if s is not None and cat.get("lo", 0) <= s <= cat.get("hi", 0):
                out.append(cat)
        elif kind == "am":                               # A<=a_hi, M<=m_hi, A+M>0, rank>=floor
            if s is not None and a is not None and m is not None:
                if "min_rank" in cat:
                    floor = cfg.get("rank_thresholds", {}).get(cat["min_rank"], 1007500)
                else:
                    floor = cat.get("score_min", 1007500)
                if s >= floor and a <= cat.get("a_hi", 4) and m <= cat.get("m_hi", 4) and (a + m) > 0:
                    out.append(cat)
    return out


def _sanitize(s):
    return str(s).replace("+", "p").replace("/", "_").replace("\\", "_")


def _out_name(base, ext, rank, rec, cats, rename):
    tag = "+".join(_sanitize(c["key"]) for c in cats)
    if rename:
        return "%s__%s_%s_A%sM%s_%s%s" % (
            base, tag, _sanitize(rank or "NA"), rec.get("attack"),
            rec.get("miss"), rec.get("score"), ext)
    return "%s__%s%s" % (base, tag, ext)


def copy_matches(path, rec, matches, cfg):
    """Copy the screenshot into each target folder for its matched categories."""
    by_folder = {}
    for c in matches:
        by_folder.setdefault(c.get("folder", cfg.get("cun_folder", "寸")), []).append(c)
    base, ext = os.path.splitext(os.path.basename(path))
    rank = cun_detect.rank_of(rec.get("score"), cfg)
    rename = cfg.get("rename_with_stats", True)
    copied = []
    for folder, cats in by_folder.items():
        parts = str(folder).replace("\\", "/").split("/")     # support nested e.g. 寸/AJ寸
        d = os.path.join(cfg["output_root"], *parts)
        try:
            os.makedirs(d, exist_ok=True)
            dst = os.path.join(d, _out_name(base, ext, rank, rec, cats, rename))
            if not os.path.exists(dst):
                shutil.copy2(path, dst)
            copied.append(dst)
        except Exception as e:
            log("ERROR copying %s -> %s: %s" % (os.path.basename(path), folder, e))
    return copied


def clear_tool_files(cfg):
    """Remove only files this tool created (named '*__*') from the output folders."""
    removed = 0
    folders = set(c.get("folder") for c in cfg.get("categories", []) if c.get("folder"))
    folders |= {cfg.get("cun_folder", "寸"), cfg.get("aj_folder", "AJ")}
    for folder in folders:
        d = os.path.join(cfg["output_root"], folder)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if "__" in f and f.lower().endswith(".png"):
                try:
                    os.remove(os.path.join(d, f)); removed += 1
                except Exception:
                    pass
    return removed


# ----------------------------- scan / stats ---------------------------------
def scan_all(cfg, progress=None, rebuild=False, reocr=False):
    cache = {} if reocr else load_cache()
    sdir = cfg["screenshots_dir"]
    files = sorted(list_pngs(sdir))
    if rebuild:
        clear_tool_files(cfg)
    n_cun = n_aj = 0
    CUN_KINDS = {"score", "am", "ajcun"}
    for i, f in enumerate(files, 1):
        rec = get_ocr(os.path.join(sdir, f), cfg, cache)
        matches = classify(rec, cfg)
        if matches:
            copy_matches(os.path.join(sdir, f), rec, matches, cfg)
            kinds = set(c.get("kind") for c in matches)
            if kinds & CUN_KINDS:
                n_cun += 1
            if "aj" in kinds:
                n_aj += 1
        if progress and i % 5 == 0:
            progress(i, len(files), n_cun, n_aj)
        if i % 25 == 0:
            save_cache(cache)
    save_cache(cache)
    if progress:
        progress(len(files), len(files), n_cun, n_aj)
    return {"total": len(files), "cun": n_cun, "aj": n_aj}


def daily_counts(cfg, cache=None):
    """Return sorted [(date, cun_count, aj_count), ...] derived from cache+config."""
    if cache is None:
        cache = load_cache()
    days = {}
    cun_kinds = {"score", "am", "ajcun"}
    for fn, rec in cache.items():
        mobj = _DATE_RE.match(fn)
        if not mobj:
            continue
        date = mobj.group(1)
        kinds = set(c.get("kind") for c in classify(rec, cfg))
        d = days.setdefault(date, [0, 0])
        if kinds & cun_kinds:
            d[0] += 1
        if "aj" in kinds:
            d[1] += 1
    return [(k, v[0], v[1]) for k, v in sorted(days.items())]


# ----------------------------- watcher ---------------------------------------
def _settled(sdir, f, now):
    try:
        return now - os.path.getmtime(os.path.join(sdir, f)) >= SETTLE_SEC
    except OSError:
        return False


class Watcher(threading.Thread):
    """Persistent, game-aware watcher. Detects the game by polling the process
    list (no need to modify start.bat). Only screenshots that appear AFTER it
    starts are auto-processed (existing backlog is left to scan_all)."""

    def __init__(self, get_cfg, on_match=None, on_status=None):
        super().__init__(daemon=True)
        self.get_cfg = get_cfg
        self.on_match = on_match
        self.on_status = on_status
        self._stop = threading.Event()
        self.cache = load_cache()
        self._cache_lock = threading.Lock()

    def stop(self):
        self._stop.set()

    def _status(self, msg):
        log(msg)
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    def _handle(self, path, cfg):
        with self._cache_lock:
            rec = get_ocr(path, cfg, self.cache)
            matches = classify(rec, cfg)
            if matches:
                copy_matches(path, rec, matches, cfg)
            save_cache(self.cache)
        if matches:
            keys = "+".join(c["key"] for c in matches)
            log("[MATCH] %s score=%s A=%s M=%s -> %s"
                % (os.path.basename(path), rec.get("score"), rec.get("attack"),
                   rec.get("miss"), keys))
            if self.on_match:
                try:
                    self.on_match(os.path.basename(path), rec, matches)
                except Exception:
                    pass
        return bool(matches)

    def run(self):
        set_idle_priority()
        cfg = self.get_cfg()
        sdir = cfg["screenshots_dir"]
        baseline = set(list_pngs(sdir))
        self._status("watcher started | mode=%s | watching %s (%d existing ignored)"
                     % (cfg.get("process_mode"), sdir, len(baseline)))
        seen = set()
        queue = []
        game_prev = False
        last_game = 0.0
        flush_at = None
        while not self._stop.is_set():
            cfg = self.get_cfg()
            mode = cfg.get("process_mode", "realtime")
            game = cfg.get("game_process", "chusanApp.exe")
            now = time.time()
            current = list_pngs(sdir)
            ready = [f for f in current
                     if f not in baseline and f not in seen and _settled(sdir, f, now)]
            for f in sorted(ready):
                seen.add(f)
                if mode == "on_close":
                    queue.append(f)
                else:
                    self._handle(os.path.join(sdir, f), cfg)

            if now - last_game >= cfg.get("game_poll_sec", 4):
                last_game = now
                running = is_process_running(game)
                if running != game_prev:
                    game_prev = running
                    self._status("game %s" % ("running" if running else "closed"))
                    if not running and mode == "on_close" and queue:
                        flush_at = now + cfg.get("game_exit_grace_sec", 20)

            if flush_at and now >= flush_at:
                flush_at = None
                # final sweep: include anything that appeared since
                extra = [f for f in list_pngs(sdir)
                         if f not in baseline and f not in seen]
                for f in sorted(set(queue) | set(extra)):
                    seen.add(f)
                    self._handle(os.path.join(sdir, f), cfg)
                self._status("on_close batch processed (%d)" % len(queue))
                queue = []

            self._stop.wait(POLL_SEC)
        self._status("watcher stopped")
