# -*- coding: utf-8 -*-
"""
CHUNITHM result-screen OCR core.

detect(path) -> {score, attack, miss, rank, ...}  (no classification here;
classification into AJ / 寸 categories lives in cun_core.py).

Validated strategy on real 1920x1080 result screenshots:
  * Top status bar (clean upright font). We isolate the dark text outline
    (dark<th -> black) so the white numbers become crisp:
      - line 1 -> ATTACK, MISS  (the overlay HIDES a stat when it is 0, so
        "label present" <=> ">=1" and "label absent" <=> "==0")
      - line 2 -> SCORE (longest 6-7 digit token; psm6 fallback for split tokens)
  * Native breakdown box (bright digits on purple) is a lazy fallback used only
    when a shown top-bar value fails to parse.
The big rainbow SCORE/RANK glyphs are intentionally NOT OCR'd (ornate italic
font is unreliable); the top-bar score gives an exact number.
"""
import os, re, json, sys, shutil

from PIL import Image
import pytesseract

def data_dir():
    """Folder that holds cun_config.json / cache / log / icon. Works whether
    running as .py, a one-file exe, or a one-dir exe placed in a subfolder
    (then the config in the parent install folder is used)."""
    if getattr(sys, "frozen", False):
        d = os.path.dirname(sys.executable)
        if not os.path.exists(os.path.join(d, "cun_config.json")):
            parent = os.path.dirname(d)
            if os.path.exists(os.path.join(parent, "cun_config.json")):
                return parent
        return d
    return os.path.dirname(os.path.abspath(__file__))


HERE = data_dir()
CONFIG_PATH = os.path.join(HERE, "cun_config.json")

DEFAULTS = {
    "screenshots_dir": "",
    "output_root": "",
    "cun_folder": "寸",
    "aj_folder": "AJ",
    "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "process_mode": "realtime",
    "game_process": "chusanApp.exe",
    "game_poll_sec": 4,
    "game_exit_grace_sec": 20,
    "rename_with_stats": True,
    "expected_size": [1920, 1080],
    "dark_threshold": 95,
    "bright_threshold": 110,
    "boxes": {
        "top_line1": [558, 6, 1345, 40],
        "top_line2": [760, 42, 1345, 82],
        "bd_atk":   [824, 758, 921, 792],
        "bd_miss":  [824, 806, 921, 840],
    },
    "rank_thresholds": {
        "SSS+": 1009000, "SSS": 1007500, "SS+": 1005000, "SS": 1000000,
        "S+": 990000, "S": 975000, "AAA": 950000, "AA": 925000, "A": 900000,
        "BBB": 800000, "BB": 700000, "B": 600000, "C": 500000, "D": 0,
    },
    "categories": [
        {"key": "AJ", "label": "AJ", "kind": "aj", "enabled": True, "folder": "AJ"},
        {"key": "FC", "label": "FC", "kind": "fc", "enabled": True, "folder": "FC"},
        {"key": "AJ寸", "label": "AJ 寸", "kind": "ajcun", "enabled": True, "folder": "寸/AJ寸", "m_hi": 4},
        {"key": "SSS+寸", "label": "SSS+ 寸", "kind": "score", "enabled": True, "folder": "寸/SSS+寸", "lo": 1008600, "hi": 1008999},
        {"key": "SSS寸", "label": "SSS 寸", "kind": "score", "enabled": True, "folder": "寸/SSS寸", "lo": 1007000, "hi": 1007499},
        {"key": "SS+寸", "label": "SS+ 寸", "kind": "score", "enabled": True, "folder": "寸/SS+寸", "lo": 1004500, "hi": 1004999},
        {"key": "SS寸", "label": "SS 寸", "kind": "score", "enabled": True, "folder": "寸/SS寸", "lo": 999500, "hi": 999999},
        {"key": "AM寸", "label": "ATTACK+MISS", "kind": "am", "enabled": True, "folder": "寸/AM寸", "a_hi": 4, "m_hi": 4, "min_rank": "SSS"},
    ],
}


def load_config(path=CONFIG_PATH):
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if v is not None:
                    if k == "boxes" and isinstance(v, dict):
                        cfg["boxes"].update(v)
                    else:
                        cfg[k] = v
        except Exception as e:
            sys.stderr.write("config load failed (%s); using defaults\n" % e)

    # Auto-resolve screenshot/output paths relative to the install when not set,
    # so the tool is portable: drop the "cun" folder into <CHUNITHM>\bin and it
    # finds <CHUNITHM>\bin\screenshots automatically.
    base = os.path.dirname(HERE)
    if not cfg.get("screenshots_dir"):
        cfg["screenshots_dir"] = os.path.normpath(os.path.join(base, "screenshots"))
    if not cfg.get("output_root"):
        cfg["output_root"] = cfg["screenshots_dir"]

    # Tesseract: prefer the configured path; otherwise fall back to PATH.
    tc = cfg.get("tesseract_cmd") or ""
    if not os.path.exists(tc):
        found = shutil.which("tesseract")
        if found:
            tc = found
        cfg["tesseract_cmd"] = tc
    pytesseract.pytesseract.tesseract_cmd = cfg["tesseract_cmd"]
    return cfg


def save_config(cfg, path=CONFIG_PATH):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def rank_of(score, cfg):
    if score is None:
        return None
    pairs = sorted(cfg["rank_thresholds"].items(), key=lambda kv: kv[1], reverse=True)
    for name, thr in pairs:
        if score >= thr:
            return name
    return "D"


# --------------------------- OCR primitives ---------------------------------
def _scaled_box(box, w, h, exp):
    if [w, h] == list(exp):
        return tuple(box)
    sx, sy = w / exp[0], h / exp[1]
    return (int(box[0]*sx), int(box[1]*sy), int(box[2]*sx), int(box[3]*sy))


def _gray(region, scale=4):
    return region.convert("L").resize((region.width*scale, region.height*scale), Image.LANCZOS)


def _prep_topbar(region, dark_th):
    return _gray(region).point(lambda p: 0 if p < dark_th else 255)


def _prep_breakdown(region, bright_th):
    return _gray(region).point(lambda p: 0 if p > bright_th else 255)


def _ocr(im, psm=7, whitelist=None):
    cfg = "--psm %d" % psm
    if whitelist:
        cfg += " -c tessedit_char_whitelist=%s" % whitelist
    return pytesseract.image_to_string(im, config=cfg).strip()


def _find_int(pattern, text, lo=None, hi=None):
    for m in re.finditer(pattern, text, re.I):
        try:
            v = int(m.group(1))
        except (ValueError, IndexError):
            continue
        if (lo is None or v >= lo) and (hi is None or v <= hi):
            return v
    return None


def _parse_score(text):
    """Pick the score (6-7 digit number) from a line-2 OCR string. Collapses
    stray spaces between digit groups (e.g. '1,007 ,603') so split scores parse."""
    text = re.sub(r"(?<=[\d,])\s+(?=[\d,])", "", text)
    cands = []
    for tok in re.findall(r"[\d,]+", text):
        d = re.sub(r"\D", "", tok)
        if 6 <= len(d) <= 7:
            v = int(d)
            if 100000 <= v <= 1010000:
                cands.append(v)
    return max(cands) if cands else None


def detect(path, cfg=None):
    if cfg is None:
        cfg = load_config()
    out = {"file": os.path.basename(path), "path": path, "score": None,
           "attack": None, "miss": None, "rank": None, "note": "",
           "raw_line1": "", "raw_line2": ""}
    try:
        img = Image.open(path)
    except Exception as e:
        out["note"] = "open_failed: %s" % e
        return out
    w, h = img.size
    exp = cfg["expected_size"]
    B = cfg["boxes"]
    dark_th, bright_th = cfg["dark_threshold"], cfg["bright_threshold"]

    t1 = _ocr(_prep_topbar(img.crop(_scaled_box(B["top_line1"], w, h, exp)), dark_th), psm=7)
    l2_img = _prep_topbar(img.crop(_scaled_box(B["top_line2"], w, h, exp)), dark_th)
    t2 = _ocr(l2_img, psm=7)
    out["raw_line1"], out["raw_line2"] = t1, t2

    # ATTACK / MISS: label present <=> >=1 ; label absent <=> 0 (overlay hides 0)
    ut = t1.upper()

    def top_field(label, regex):
        if label not in ut:
            return 0, "zero"
        m = re.search(regex, t1, re.I)
        if m:
            return int(m.group(1)), "top"
        return None, "unread"

    attack, asrc = top_field("ATTACK", r"ATTACK\D{0,4}(\d{1,4})")
    miss, msrc = top_field("MISS", r"MISS\D{0,4}(\d{1,4})")

    score = _parse_score(t2)
    if score is None:
        t2b = _ocr(l2_img, psm=6)
        s2 = _parse_score(t2b)
        if s2 is not None:
            score = s2
            out["raw_line2"] = t2 + " || psm6:" + t2b

    notes = []
    if asrc == "unread":
        bd = _find_int(r"(\d{1,4})", _ocr(_prep_breakdown(img.crop(_scaled_box(B["bd_atk"], w, h, exp)), bright_th), psm=8, whitelist="0123456789"), 0, 9999)
        if bd is not None:
            attack = bd; notes.append("attack_from_breakdown")
    if msrc == "unread":
        bd = _find_int(r"(\d{1,4})", _ocr(_prep_breakdown(img.crop(_scaled_box(B["bd_miss"], w, h, exp)), bright_th), psm=8, whitelist="0123456789"), 0, 9999)
        if bd is not None:
            miss = bd; notes.append("miss_from_breakdown")

    out["score"], out["attack"], out["miss"] = score, attack, miss
    out["rank"] = rank_of(score, cfg)
    out["note"] = ";".join(notes)
    return out


def _main(argv):
    cfg = load_config()
    args = [a for a in argv if not a.startswith("--")]
    if "--all" in argv:
        d = cfg["screenshots_dir"]
        args = sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".png"))
    for p in args:
        r = detect(p, cfg)
        print("%-26s score=%-9s rank=%-4s A=%-4s M=%-4s %s" % (
            r["file"], r["score"], r["rank"], r["attack"], r["miss"],
            ("[" + r["note"] + "]") if r["note"] else ""))


if __name__ == "__main__":
    _main(sys.argv[1:])
