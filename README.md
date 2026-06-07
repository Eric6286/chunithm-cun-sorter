<div align="center">

<img src="奶奶蛙.png" width="120" alt="奶奶蛙">

# 今天你寸了吗

**CHUNITHM「寸」成绩自动识别 + 全截图归档工具**
*Auto-detect near-miss CHUNITHM results & organize every screenshot — WinUI 3 / Fluent 2 / Mica.*

</div>

---

本工具用 OCR 读取结算画面的 **得分 / ATTACK / MISS**：

- 按你**自定义的判定规则**把「寸」成绩**复制**到独立文件夹并统计；
- 还能把**所有截图**按 **日期 / 评级 / 达成（AJ·FC）** 自动**整理归档**（维度可拖动排序、自由嵌套）。

并提供一个 **Fluent 2 + Win11 Mica** 风格的图形界面来配置规则、查看每日 **寸 / AJ / FC** 曲线。

搭配幻台使用风味更佳哦~

> 「寸」判定**只复制原图**；一旦开启「整理」，原始截图会被**移动**到归档文件夹（只移动、不删除，可还原）。识别只在结算画面发生、以最低 CPU 优先级运行，不影响游戏帧数。

> 本项目使用 **WinUI 3 + .NET 8**（Windows App SDK）开发。最新版本：[**Release v1.2**](https://github.com/Eric6286/chunithm-cun-sorter/releases/latest)（自包含构建，**免装 .NET 运行时**）。

## ✨ 功能特性

- 🎯 **自定义判定规则**（用于「寸」统计）：**评级判定**（SSS+寸 / SSS寸 / SS+寸 / SS寸 预设，下限可调，也可自定义区间）、**AJ寸**、**ATTACK+MISS**；每条可增删、可开关
- 🗂️ **整理归档**（可选）：按 **日期（年/月/日）**、**评级**、**达成（AJ/FC/普通）** 三个维度归档；**拖动或 ↑↓ 调顺序**决定文件夹嵌套（靠上＝外层）；开启后把原图**移动**到对应文件夹
- 🖼️ Fluent 2 设计 + Win11 Mica 模糊 + **深色标题栏**；切换页面带淡入过渡动画
- 📈 每日 **寸 / AJ / FC** 数量曲线 + 统计卡片（今天 / 近 7 天 / 累计 / 最高一天）
- 🐢 低占用：结算画面才识别、IDLE 优先级、OCR 结果缓存；可选「关游戏后再处理」模式
- 🎮 通过**轮询进程**检测游戏启停，**无需改动 `start.bat`**
- 🔔 系统托盘常驻、可开机自启
- 📦 自包含发布，运行**不需要安装 .NET 或 Python**

## 🧩 运行要求

- **Windows 10 1809+ / 11**，x64
- **Tesseract OCR**（OCR 引擎，必需）：<https://github.com/UB-Mannheim/tesseract/wiki>
  装到默认路径 `C:\Program Files\Tesseract-OCR\` 即可（程序会自动使用其 `tessdata`）；
  或把含 `eng.traineddata` 的 `tessdata` 文件夹放到 exe 同级目录；也可在 `cun_config.json` 里改 `tesseract_cmd`。
- 截图分辨率 **1920×1080**（其它分辨率会按比例自动缩放识别区域，但 1080p 最稳）
- *（仅从源码构建时）* **.NET 8 SDK**

## 🚀 快速开始

### 方式一：下载 Release（推荐，免装 .NET / Python）
1. 安装 **Tesseract OCR**（见上）。
2. 下载最新 **`chunithm-cun-sorter_v1.2_win64.zip`**，解压得到 `cun` 文件夹，放到你的 **`<CHUNITHM>\bin\`** 里（即与 `screenshots` 同级，最终为 `<CHUNITHM>\bin\cun\`）。
3. 双击 **`app\今天你寸了吗.exe`** 启动（可右键「发送到 → 桌面快捷方式」方便以后打开）。
4. 在「配置」页设好**截图目录**、添加**判定规则**、按需开启**整理**；游戏照常用 `start.bat` 启动，让程序常驻即可自动归档。点「应用并重新扫描」可整理历史截图。

> 截图目录默认自动取 **`<安装目录上级>\screenshots`**；若不在那儿，在「配置 → 目录设置」用「浏览…」手动指定即可（也可直接改 `cun_config.json` 的 `screenshots_dir`）。

### 方式二：从源码构建运行
```powershell
dotnet restore
dotnet build -c Release
dotnet run --project CunSorter -c Release
```

### 打包为独立文件夹（免装 .NET 运行时）
```powershell
dotnet publish CunSorter/CunSorter.csproj -c Release -r win-x64 --self-contained `
  -p:Platform=x64 -p:WindowsAppSDKSelfContained=true -o publish_out
```
把 `publish_out` 的内容放进 **`<CHUNITHM>\bin\cun\app\`**，并在其上级 `cun\` 放一份 `cun_config.json` 即可。

> **发版**：仓库带有 `release.yml`，**推送一个 `v*` tag**（如 `git tag v1.2 && git push origin v1.2`）就会在 Windows runner 上自动构建自包含包并发布 GitHub Release。

## 🖥️ 界面说明（三页）

- **配置**
  - **目录设置**：截图目录（要扫描的原图）/ 输出目录（分类结果根目录），均可「浏览…」选择。
  - **判定规则（寸）**：自定义规则列表，点「添加判定规则」→ 选**评级判定 / AJ寸 / ATTACK+MISS**；命中的图会**复制**到 `寸/` 下并计入统计。每条可删除。
  - **整理**：`根据日期整理` / `根据评级整理` / `根据达成整理` 三行，各自开关；**拖动或 ↑↓ 排序**决定嵌套层级。**开启任一项后，扫描会把原图移动到对应文件夹。**
  - `保存配置` / `应用并重新扫描`（按当前规则后台重建，不卡界面）/ `打开输出文件夹`
- **统计**：每日 **寸 / AJ / FC** 数量曲线 + 今天 / 近 7 天 / 累计 / 最高一天。
- **运行**：切换 `realtime` / `on_close` 模式、启停监视、显示游戏状态、最近命中、开机自启。
  监视运行时关闭窗口会**最小化到托盘**继续后台监视（右键托盘可显示主界面或退出）。

## 🏷️ 判定与整理

### 判定规则（「寸」统计，复制原图）
| 类型 | 判定 | 说明 |
|---|---|---|
| **评级判定** | `下限 ≤ 得分 ≤ 上限` | 预设档位 `SSS+寸 / SSS寸 / SS+寸 / SS寸`（下限可改、上限固定），或选「自定义区间」自由设上下限 |
| **AJ寸** | `ATTACK=0 且 0<MISS≤x` | 差一点 AJ |
| **ATTACK+MISS** | `ATTACK≤a 且 MISS≤m 且 A+M>0，评级≥门槛` | |

> 评价分数段：SSS+ `≥1,009,000`、SSS `≥1,007,500`、SS+ `≥1,005,000`、SS `≥1,000,000` …（满分 1,010,000）。
> 一张截图可同时命中多条规则，会分别复制到各自子文件夹，文件名标注命中类别与成绩，例如 `2026-05-29_08-18-04__SSS寸_SSS_A2M0_1008792.png`。

### 整理维度（移动原图）
| 维度 | 生成文件夹 |
|---|---|
| **日期** | `2026` / `2026-05` / `2026-05-24`（按年 / 月 / 日） |
| **评级** | `SSS+` / `SSS` / `SS+` / `SS` / …（满分段评级） |
| **达成** | `AJ`（A0 M0）/ `FC`（无 MISS）/ `普通` |

> 顺序决定嵌套：如「日期」在上、「评级」在下且都开启 → `2026-05/SSS+/图.png`。
> AJ / FC 属于**整理**（达成维度），不计入「寸」。

## ⚙️ 配置 `cun_config.json`

| 键 | 说明 |
|---|---|
| `screenshots_dir` | 监视的截图目录（留空则自动取 `<安装目录上级>\screenshots`） |
| `output_root` | 输出根目录（留空则同 `screenshots_dir`） |
| `tesseract_cmd` | Tesseract 路径（用于定位 `tessdata`；留空 / 找不到时回退到 PATH） |
| `process_mode` | `realtime`（实时·低优先级）或 `on_close`（关游戏后处理） |
| `game_process` | 检测用进程名（默认 `chusanApp.exe`） |
| `rename_with_stats` | 复制时在文件名追加成绩与类别 |
| `rank_thresholds` | 各评级分数线 |
| `categories[]` | **自定义判定规则**（`enabled / kind / folder` + 各自参数）；初始为空，由界面增删 |
| `organize.steps[]` | **整理维度与顺序**：每项含 `kind`（`date` / `rank` / `achievement`）、`enabled`、`date_span`（`year` / `month` / `day`，仅 date 用）。列表顺序即文件夹嵌套顺序 |
| `boxes` / `dark_threshold` / `bright_threshold` | OCR 区域与阈值（基于 1920×1080） |

> **数据目录定位**：程序从 exe 所在目录起**逐级向上**查找 `cun_config.json`——所以正式部署把 exe 放在 `bin\cun\app\`、配置放 `bin\cun\` 即可自动找到；`dotnet run` 调试时也能向上定位到仓库里的配置。

## 🔬 工作原理

读取结算画面**顶部状态栏**的清晰字体：隔离白字的深色描边 → 用 Tesseract 识别 `SCORE / ATTACK / MISS`，
由得分换算评级（顶栏在某项为 0 时会隐藏该项，据此判 0）。大号彩虹分数/评级因字体花哨**不**直接 OCR。
OCR 结果缓存在 `cun_ocr_cache.json`，改区间后重新判定是**瞬间**完成的（无需重新识别）。

## 📁 目录结构

```
.
├─ CunSorter.sln
├─ CunSorter/
│  ├─ CunSorter.csproj
│  ├─ App.xaml(.cs) / MainWindow.xaml(.cs)
│  ├─ Models/        # CunConfig / Category / OrganizeConfig / OcrResult
│  ├─ Services/      # OCR / 配置 / 分类·整理·扫描 / 监视 / 自启 / 原生工具
│  ├─ Pages/         # 配置 / 统计 / 运行 三页
│  └─ Assets/        # icon.ico / 奶奶蛙.png
├─ cun_config.json   # 种子配置（界面读写；发版时随包附带）
├─ 奶奶蛙.png         # 图标源图
├─ .github/workflows/ # build.yml（编译 CI）/ release.yml（tag 触发发版）
└─ LICENSE
```

各 `Services` 模块职责：`OcrService`（结算画面 OCR）、`ConfigService`（配置读写 / 路径解析 / 评级）、
`ClassifierService`（分类 / 复制 / 整理移动 / 扫描 / 缓存 / 每日统计）、`WatcherService`（游戏感知后台监视）、
`AutostartService`（开机自启）、`NativeUtil`（进程检测 / IDLE 优先级 / 数据目录 / 深色标题栏）。

## ❓ FAQ

- **识别不到 / 全是空？** 确认是 1920×1080 截图、装了 Tesseract（且能找到 `eng.traineddata`），且截图目录指向正确。
- **提示找不到 OCR 引擎？** 装一下 Tesseract OCR，或把含 `eng.traineddata` 的 `tessdata` 放到 exe 同级 / 配好 `tesseract_cmd`。
- **开了整理后原图不见了？** 整理是把原图**移动**到归档文件夹（如 `日期/评级/达成`），不是删除；在输出目录对应子文件夹里能找到，可手动移回。
- **会不会掉帧？** 识别只在结算画面、IDLE 优先级；或把 `process_mode` 设为 `on_close`，游戏中零识别。

## 🙏 致谢

- [Windows App SDK / WinUI 3](https://learn.microsoft.com/windows/apps/winui/winui3/) · [H.NotifyIcon](https://github.com/HavenDV/H.NotifyIcon) · [Tesseract .NET](https://github.com/charlesw/tesseract)
- OCR 引擎：[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

## 📄 许可

[MIT](LICENSE)。本项目为非官方同人工具，与 SEGA 无关；CHUNITHM 及相关素材归 SEGA 所有。
