# 从存量归档统计生成「结算成绩画面」像素指纹（CaptureService 用）。
#
# 正样本：screenshots 下 AJ / FC / 普通 三棵树的归档原图（真·成绩画面）。
# 负样本：--neg 传入的帧（CLEAR 过场、地图推进、打歌画面等）——成绩画面
# 与 CLEAR 过场共享顶栏/铭牌等 chrome，指纹点必须能把两者分开，所以只保留
# 「跨全部正样本恒定 且 与每一张负样本都显著不同」的点。
#
# 用法: python gen_result_signature.py [--neg 负样本1.png ...] [--exclude 文件名子串 ...]
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\Chuni\CHUNITHM\bin\screenshots")
STEP = 8            # 采样网格步长
TOL = 6             # 稳定判定：跨全部正样本 max-min ≤ TOL（每通道）
NEG_MARGIN = 60     # 判别判定：与每张负样本的通道最大差 ≥ NEG_MARGIN
RUNTIME_TOL = 24    # 运行时匹配容差（与 CaptureService.MatchTol 一致）
PICKS = 24

parser = argparse.ArgumentParser()
parser.add_argument("--neg", nargs="*", default=[], help="负样本帧（CLEAR 过场 / 地图 / 打歌）")
parser.add_argument("--exclude", nargs="*", default=[], help="从正样本剔除的文件名子串")
args = parser.parse_args()

W, H = 1920, 1080

def load(p):
    im = Image.open(p).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H))
    return np.asarray(im, dtype=np.int16)

imgs = []
for sub in ("AJ", "FC", "普通"):
    d = ROOT / sub
    if d.exists():
        imgs += [p for p in d.rglob("*.png")
                 if "__" not in p.name and not any(x in p.name for x in args.exclude)]
print(f"positives: {len(imgs)}, negatives: {len(args.neg)}")

gx = np.arange(0, W, STEP)
gy = np.arange(0, H, STEP)
mins = maxs = None
used = 0
for p in imgs:
    try:
        im = Image.open(p).convert("RGB")
    except Exception:
        continue
    if im.size != (W, H):
        continue
    a = np.asarray(im, dtype=np.int16)[np.ix_(gy, gx)]
    if mins is None:
        mins = a.copy(); maxs = a.copy()
    else:
        np.minimum(mins, a, out=mins)
        np.maximum(maxs, a, out=maxs)
    used += 1
print(f"used {used} positives at {W}x{H}")

stable = (maxs - mins).max(axis=2) <= TOL
mean = ((mins + maxs) / 2).astype(int)
bright = mean.max(axis=2)
ok = stable & (bright > 40)          # 不太黑，避免匹配任意黑屏
print(f"stable & non-dark: {ok.sum()}")

# 判别性：与每张负样本在该点的通道最大差 ≥ NEG_MARGIN
for np_path in args.neg:
    neg = load(np_path)[np.ix_(gy, gx)]
    diff = np.abs(neg - mean).max(axis=2)
    ok &= diff >= NEG_MARGIN
    print(f"  after neg {Path(np_path).name}: {ok.sum()}")

cand = np.argwhere(ok)
if not len(cand):
    raise SystemExit("no discriminative stable points — lower NEG_MARGIN?")

# 均匀挑点：位置分桶，桶内选饱和度+亮度最高的
sat = mean.max(axis=2) - mean.min(axis=2)
buckets = {}
for (iy, ix) in cand:
    key = (iy // 12, ix // 20)
    s = sat[iy, ix] * 2 + bright[iy, ix]
    if key not in buckets or s > buckets[key][0]:
        buckets[key] = (s, iy, ix)
ranked = sorted(buckets.values(), key=lambda t: -t[0])[:PICKS]
picked = []
for (_, iy, ix) in ranked:
    x, y = int(gx[ix]), int(gy[iy])
    r, g, b = (int(v) for v in mean[iy, ix])
    picked.append({"x": x, "y": y, "r": r, "g": g, "b": b})
print(json.dumps(picked, ensure_ascii=False))

# C# 常量输出
parts = [f"({p['x']}, {p['y']}, {p['r']}, {p['g']}, {p['b']})" for p in picked]
print("C#:")
for i in range(0, len(parts), 3):
    print("        " + ", ".join(parts[i:i + 3]) + ",")

# 验证
def score(path):
    a = load(path)
    n = 0
    for pt in picked:
        px = a[pt["y"], pt["x"]]
        if max(abs(int(px[0]) - pt["r"]), abs(int(px[1]) - pt["g"]),
               abs(int(px[2]) - pt["b"])) <= RUNTIME_TOL:
            n += 1
    return n

need = round(len(picked) * 0.9)
worst = len(picked); fails = 0
for p in imgs:
    try:
        n = score(p)
    except Exception:
        continue
    worst = min(worst, n)
    if n < need:
        fails += 1; print(f"  POSITIVE FAIL {p.name}: {n}/{len(picked)}")
print(f"positive check: fails={fails}/{used}, worst={worst}/{len(picked)}, threshold={need}")
for np_path in args.neg:
    print(f"negative {Path(np_path).name}: {score(np_path)}/{len(picked)}")
