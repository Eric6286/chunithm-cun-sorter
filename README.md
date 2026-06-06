<div align="center">

<img src="奶奶蛙.png" width="120" alt="奶奶蛙">

# 今天你寸了吗

**CHUNITHM「寸」成绩自动识别与归档工具**
*Auto-detect & sort your near-miss CHUNITHM results — with a Fluent 2 / Mica GUI.*

</div>

---

本工具用 OCR 读取结算画面的 **得分 / ATTACK / MISS**，
把「寸」以及 **AJ / FC** 成绩**自动分类复制**到独立文件夹，
并提供一个 **Fluent 2 + Mica** 风格的图形界面来自定义规则、查看每日「寸」曲线。

搭配幻台使用风味更佳哦~

> 全程**只复制，绝不修改或删除原始截图**。低占用：识别发生在结算画面、以最低 CPU 优先级运行，不影响游戏帧数。

> 🆕 **WinUI 3 / .NET 8 移植版**已在 [`winui3/`](winui3/) 目录提供，功能与配置文件（`cun_config.json` / `cun_ocr_cache.json`）与本 Python 版完全互通，构建说明见 [winui3/README.md](winui3/README.md)。

## ✨ 功能特性

- 🎯 多种可自定义的归类规则：**AJ**、**FC**、**AJ寸**、按得分的 **SSS+ / SSS / SS+ / SS 寸**、按 **ATTACK/MISS** 的「寸」
- 🖼️ Fluent 2 设计 + Win11 Mica 模糊；每个类别可开关、数值可自由调整
- 📈 每日「寸」数量曲线图（含 AJ），带统计卡片与更新时间
- 🗂️ 不同「寸」类型分门别类放进 `寸/` 下的子文件夹
- 🐢 低占用：结算画面才识别、IDLE 优先级、OCR 结果缓存；可选「关游戏后再处理」模式
- 🎮 通过**轮询进程**检测游戏启停，**无需改动 `start.bat`**
- 🔔 系统托盘常驻、可开机自启
- 📦 可打包为独立 `.exe`（运行不需要 Python）

## 🧩 运行要求

- **Windows 10 / 11**
- **Tesseract OCR**（OCR 引擎，必需）：<https://github.com/UB-Mannheim/tesseract/wiki>
  装到默认路径 `C:\Program Files\Tesseract-OCR\` 或加入 PATH 即可；否则在 `cun_config.json` 里改 `tesseract_cmd`。
- 截图分辨率 **1920×1080**（其它分辨率会按比例自动缩放识别区域，但 1080p 最稳）
- *（从源码运行时）* Python 3.10+

## 🚀 快速开始

### 方式一：下载 Release（推荐，免装 Python）
1. 安装 **Tesseract OCR**（见上）。
2. 下载 Release 压缩包，解压得到 `cun` 文件夹，放到你的 **`<CHUNITHM>\bin\`** 里（即与 `screenshots` 同级，最终为 `<CHUNITHM>\bin\cun\`）。
3. 双击 **`app\今天你寸了吗.exe`** 启动（可右键「发送到 → 桌面快捷方式」方便以后打开）。
4. 游戏照常用 `start.bat` 启动；让本程序常驻即可自动归档。点「应用并重新扫描」可整理历史截图。

> 若你的截图目录不在 `<CHUNITHM>\bin\screenshots`，打开 `cun_config.json` 把 `screenshots_dir` 改成你的路径即可。

### 方式二：从源码运行
```bat
pip install -r requirements.txt
python cun_gui.py
```

### 自行打包 exe
```bat
pip install -r requirements.txt pyinstaller
build.bat
```
产物在 `app\今天你寸了吗.exe`。

## 🖥️ 界面说明（三页）

- **规则设置**：每个类别一个开关；按得分的档位上限已固定、只可改下限；ATTACK+MISS 档可分别设 ATTACK / MISS 上限和评级门槛。
  - `保存配置`：写入 `cun_config.json`
  - `应用并重新扫描`：按当前规则**重建**输出文件夹（后台进行，不卡界面）
  - `打开输出文件夹`
- **统计**：每日「寸」数量曲线（另含 AJ 线）+ 今天 / 近 7 天 / 累计 / 最高一天。
- **运行**：切换 `realtime` / `on_close` 模式、启停监视、显示游戏状态、最近命中、开机自启。
  关闭窗口会**最小化到托盘**继续后台监视。

## 🏷️ 归类规则与默认值

| 类别 | 默认判定 | 输出文件夹 |
|---|---|---|
| **AJ** | `ATTACK=0 且 MISS=0` | `AJ` |
| **FC** | `ATTACK≠0 且 MISS=0` | `FC` |
| **AJ 寸** | `ATTACK=0 且 0<MISS≤x`（x 默认 4） | `寸/AJ寸` |
| **SSS+ 寸** | 得分 `1,008,600 ~ 1,008,999` | `寸/SSS+寸` |
| **SSS 寸** | 得分 `1,007,000 ~ 1,007,499` | `寸/SSS寸` |
| **SS+ 寸** | 得分 `1,004,500 ~ 1,004,999` | `寸/SS+寸` |
| **SS 寸** | 得分 `999,500 ~ 999,999` | `寸/SS寸` |
| **ATTACK+MISS** | `ATTACK≤a 且 MISS≤m 且 A+M>0`，且 `评级 ≥ SSS` | `寸/AM寸` |

> 评价分数段：SSS+ `≥1,009,000`、SSS `≥1,007,500`、SS+ `≥1,005,000`、SS `≥1,000,000` …（满分 1,010,000）。
> 一张截图可同时命中多个类型，会分别复制到各自子文件夹，文件名标注命中类别，例如
> `2026-05-29_08-18-04__AM寸_SSS_A2M0_1008792.png`。

## ⚙️ 配置 `cun_config.json`

| 键 | 说明 |
|---|---|
| `screenshots_dir` | 监视的截图目录（留空则自动取 `<安装目录的上级>\screenshots`） |
| `output_root` | 输出根目录（留空则同 `screenshots_dir`） |
| `tesseract_cmd` | Tesseract 路径（留空 / 找不到时回退到 PATH） |
| `process_mode` | `realtime`（实时·低优先级）或 `on_close`（关游戏后处理） |
| `game_process` | 检测用进程名（默认 `chusanApp.exe`） |
| `rename_with_stats` | 复制时在文件名追加成绩与类别 |
| `rank_thresholds` | 各评级分数线 |
| `categories[]` | 规则列表：`enabled / kind / folder` + 各自参数 |
| `boxes` / `dark_threshold` / `bright_threshold` | OCR 区域与阈值（基于 1920×1080） |

## 🔬 工作原理

读取结算画面**顶部状态栏**的清晰字体：隔离白字的深色描边 → 识别 `SCORE / ATTACK / MISS`，
由得分换算评级（顶栏在某项为 0 时会隐藏该项，据此判 0）。大号彩虹分数/评级因字体花哨**不**直接 OCR。
OCR 结果缓存在 `cun_ocr_cache.json`，改区间后重新判定是**瞬间**完成的（无需重新识别）。

## 📁 目录结构

```
cun/
├─ app/今天你寸了吗.exe    # 主程序（双击运行；build.bat 生成，不入库走 Release）
├─ scan_all.bat           # 历史截图批量整理（源码模式）
├─ build.bat              # 打包 exe
├─ cun_gui.py             # 图形界面（Fluent 2 + Mica + 曲线图）
├─ cun_core.py            # 分类 / 复制 / 扫描 / 缓存 / 监视 / 进程检测
├─ cun_detect.py          # 结算画面 OCR
├─ cun_watcher.py         # 无界面常驻监视器（可选）
├─ scan_all.py            # 批量整理脚本
├─ cun_config.json        # 配置（界面读写）
├─ icon.ico / 奶奶蛙.png   # 应用图标 / 图标源图
├─ requirements.txt
└─ LICENSE
```

## ❓ FAQ

- **识别不到 / 全是空？** 确认是 1920×1080 截图、装了 Tesseract，且 `screenshots_dir` 指向正确目录。
- **任务栏显示成 “Python”？** 用打包后的 `app\今天你寸了吗.exe` 运行即可（已设图标与应用 ID）。
- **会不会掉帧？** 识别只在结算画面、IDLE 优先级；或把 `process_mode` 设为 `on_close`，游戏中零识别。

## 🙏 致谢

- [PySide6](https://doc.qt.io/qtforpython/) · [PySide6-Fluent-Widgets (qfluentwidgets)](https://qfluentwidgets.com/) · [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

## 📄 许可

[MIT](LICENSE)。本项目为非官方同人工具，与 SEGA 无关；CHUNITHM 及相关素材归 SEGA 所有。
