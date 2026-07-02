# 分析 CHUNITHM 结算截图，提取跨图恒定的像素指纹（结算画面检测用）
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\Chuni\CHUNITHM\bin\screenshots")
STEP = 8            # 采样网格步长
TOL = 6             # 稳定判定：跨全部图片 max-min ≤ TOL（每通道）

# 收集原图：AJ / FC / 普通 三棵树里的（都是整理过的结算原图，无 __ 副本）
imgs = []
for sub in ("AJ", "FC", "普通"):
    d = ROOT / sub
    if d.exists():
        imgs += [p for p in d.rglob("*.png") if "__" not in p.name]
root_pngs = [p for p in ROOT.glob("*.png")]   # 根目录零散图（可能是壁纸=负样本）
print(f"result candidates: {len(imgs)}, root loose: {len(root_pngs)}")

W, H = 1920, 1080
gx = np.arange(0, W, STEP)
gy = np.arange(0, H, STEP)
mins = None
maxs = None
used = 0
for p in imgs:
    try:
        im = Image.open(p).convert("RGB")
    except Exception:
        continue
    if im.size != (W, H):
        continue
    a = np.asarray(im, dtype=np.int16)[np.ix_(gy, gx)]   # (135,240,3)
    if mins is None:
        mins = a.copy(); maxs = a.copy()
    else:
        np.minimum(mins, a, out=mins)
        np.maximum(maxs, a, out=maxs)
    used += 1
print(f"used {used} images at 1920x1080")

spread = (maxs - mins).max(axis=2)          # 每点最大通道波动
stable = spread <= TOL
print(f"stable points: {stable.sum()} / {stable.size}")

mean = ((mins + maxs) / 2).astype(int)
bright = mean.max(axis=2)
# 候选：稳定且不太黑（>40 至少一通道，避免匹配任意黑屏）
cand = np.argwhere(stable & (bright > 40))
print(f"stable & non-dark: {len(cand)}")

# 均匀挑 24 个：按位置网格分桶，桶内选最"有色"的（饱和度高优先）
picked = []
if len(cand):
    sat = (mean.max(axis=2) - mean.min(axis=2))
    buckets = {}
    for (iy, ix) in cand:
        key = (iy // 17, ix // 30)          # ~8x8 桶
        s = sat[iy, ix] * 2 + bright[iy, ix]
        if key not in buckets or s > buckets[key][0]:
            buckets[key] = (s, iy, ix)
    ranked = sorted(buckets.values(), key=lambda t: -t[0])[:24]
    for (_, iy, ix) in ranked:
        x, y = int(gx[ix]), int(gy[iy])
        r, g, b = (int(v) for v in mean[iy, ix])
        picked.append({"x": x, "y": y, "r": r, "g": g, "b": b})

print(json.dumps(picked, ensure_ascii=False))

# 验证：全部结算图应通过；根目录零散图观测其匹配数
def match_count(path, pts, tol=28):
    im = Image.open(path).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H))
    a = np.asarray(im, dtype=np.int16)
    n = 0
    for pt in pts:
        px = a[pt["y"], pt["x"]]
        if max(abs(int(px[0]) - pt["r"]), abs(int(px[1]) - pt["g"]), abs(int(px[2]) - pt["b"])) <= tol:
            n += 1
    return n

if picked:
    need = int(len(picked) * 0.9)
    fails = 0
    worst = len(picked)
    for p in imgs:
        try:
            n = match_count(p, picked)
        except Exception:
            continue
        worst = min(worst, n)
        if n < need:
            fails += 1
    print(f"positive check: fails={fails}/{used}, worst match={worst}/{len(picked)}, threshold={need}")
    for p in root_pngs:
        try:
            print(f"negative {p.name}: {match_count(p, picked)}/{len(picked)}")
        except Exception as e:
            print(f"negative {p.name}: error {e}")
