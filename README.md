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

> 「寸」判定**只复制原图**；一旦开启「整理」，**识别到成绩的**结算截图会被**移动**到归档文件夹（只移动、不删除，可还原）；**无法识别的图片（壁纸、其它截图等）留在原地不动**。识别只在结算画面发生、以最低 CPU 优先级运行，不影响游戏帧数。

> 本项目使用 **WinUI 3 + .NET 8**（Windows App SDK）开发。最新版本：[**Release v1.3**](https://github.com/Eric6286/chunithm-cun-sorter/releases/latest)（自包含构建，**免装 .NET 运行时**）。

## ✨ 功能特性

- 🎯 **自定义判定规则**（用于「寸」统计）：**评级判定**（SSS+寸 / SSS寸 / SS+寸 / SS寸 预设，下限可调，也可自定义区间）、**AJ寸**、**ATTACK+MISS**；每条可增删、可开关
- 🗂️ **整理归档**（可选）：按 **日期（年/月/日）**、**评级**、**达成（AJ/FC/普通）** 三个维度归档；**拖动或 ↑↓ 调顺序**决定文件夹嵌套（靠上＝外层）；开启后把**识别到成绩的**原图**移动**到对应文件夹（无关图片不动）
- 🖼️ Fluent 2 设计 + Win11 Mica 模糊 + **深色标题栏**；切换页面带淡入过渡动画
- 📈 每日 **寸 / AJ / FC** 数量曲线 + 统计卡片（今天 / 近 7 天 / 累计 / 最高一天）
- 🐢 低占用：结算画面才识别、IDLE 优先级、OCR 结果缓存；可选「关游戏后再处理」模式
- 🎮 通过**轮询进程**检测游戏启停，**无需改动 `start.bat`**；也可选**接入 start.bat**——一键在其中注入自启动行，开游戏时本程序自动启动、开始监视并缩到托盘（原文件自动备份 `.cun-backup`，取消勾选即还原；单实例保证不重复启动）
- ⚡ **DGHub 联动**（可选）：从游戏内存**只读**判定计数（签名扫描，移植自 [Chuni2Api](https://github.com/iyxddw/Chuni2Api)），配套 **DGHub 外部插件**（`dghub-plugin/`，导入 zip 即用）：打歌中 **MISS / ATTACK** 实时触发波形；**结算时按你的「寸」规则判定**（得分由判定数换算），寸了就触发。强度 / 时长 / 波形预设 / 通道都在 **DGHub 的插件配置页**里调
- 📸 **自动截图**（可选）：曲终后由本程序**自动截取结算画面**存入截图目录（像素指纹识别结算画面，等分数滚完再存），判定数据直接取自内存——**新截图完全不需要 OCR**，可停用外部截图工具；历史图重扫仍走 OCR
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
2. 下载最新 **`chunithm-cun-sorter_v1.3_win64.zip`**，解压得到 `cun` 文件夹，放到你的 **`<CHUNITHM>\bin\`** 里（即与 `screenshots` 同级，最终为 `<CHUNITHM>\bin\cun\`）。
3. 双击 **`app\今天你寸了吗.exe`** 启动（可右键「发送到 → 桌面快捷方式」方便以后打开）。
4. 在「配置」页设好**截图目录**、添加**判定规则**、按需开启**整理**；游戏照常用 `start.bat` 启动，让程序常驻即可自动归档。点「应用并重新扫描」可整理历史截图。

> 截图目录默认自动取 **`<安装目录上级>\screenshots`**；若不在那儿，在「配置 → 目录设置」用「浏览…」手动指定即可（也可直接改 `cun_config.json` 的 `screenshots_dir`）。

### DGHub 联动（可选）
1. 下载 Release 里的 **`cun_dghub_plugin_v1.3.zip`**（或自己把仓库 `dghub-plugin/` 目录压成 zip），在 DGHub **插件中心 → 外部插件 → 导入 zip 包** 安装「今天你寸了吗 · 联动」。
2. 在 cun 的 **配置 → DGHub 联动** 打开开关并保存（默认端口 8890）。
3. 在 DGHub 里启用该插件，进插件配置页调 **MISS / ATTACK / 结算** 的开关、强度、波形预设（下拉自动列出 DGHub 的预设）和通道；「启动检查」能看到 cun 数据服务是否连上。

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
  - **DGHub 联动**：总开关 + 本机数据端口（默认 8890）。触发强度 / 波形预设 / 通道等在 **DGHub 的插件配置页**调节（见「DGHub 联动」小节）。保存后立即生效。
  - **自动截图（结算画面）**：开关 + 「等 N 秒再保存」（等结算分数滚完，默认 2.5）。开启后本开关或 DGHub 联动任一生效即运行内存读取。保存后立即生效。
  - `保存配置` / `应用并重新扫描`（按当前规则后台重建，不卡界面）/ `打开输出文件夹`
- **统计**：每日 **寸 / AJ / FC** 数量曲线 + 今天 / 近 7 天 / 累计 / 最高一天。
- **运行**：切换 `realtime` / `on_close` 模式、启停监视、显示游戏状态、联动状态（数据服务 / 判定读取）、最近命中、开机自启、**接入 start.bat**（勾选后选择游戏的 `start.bat`，注入 `start "chunithm-cun-sorter" "<exe>" --watch` 一行：开游戏即自动启动本程序、开始监视并缩到托盘；取消勾选自动移除该行）。
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
> 只整理**识别到成绩**的结算截图；某维度取不到值（如文件名没有日期）会**跳过该层**，不会建「未知」文件夹。关掉整理后，已归档到子文件夹的截图仍会被扫描与统计。

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
| `categories[]` | **自定义判定规则**（`enabled / kind / folder` + 各自参数）；初始为空，由界面增删；从 v1.1 升级时旧内置预设会被丢弃，但你手动添加 / 改过的规则会保留 |
| `organize.steps[]` | **整理维度与顺序**：每项含 `kind`（`date` / `rank` / `achievement`）、`enabled`、`date_span`（`year` / `month` / `day`，仅 date 用）。列表顺序即文件夹嵌套顺序 |
| `boxes` / `dark_threshold` / `bright_threshold` | OCR 区域与阈值（基于 1920×1080） |
| `start_bat` | 已接入的游戏 `start.bat` 路径（由「运行」页的勾选框管理；是否接入以 bat 内容为准） |
| `dghub.enabled` | DGHub 联动总开关（默认 `false`） |
| `dghub.port` | 联动数据服务监听的本机端口（默认 `8890`；触发强度 / 波形等在 DGHub 插件配置页调，不在这里） |
| `capture.enabled` | 自动截图总开关（默认 `false`） |
| `capture.delay_s` / `capture.timeout_s` | 识别到结算画面后等几秒再保存（等分数滚完，默认 2.5）/ 曲终后最多等多久（默认 30） |

> **数据目录定位**：程序从 exe 所在目录起**逐级向上**查找 `cun_config.json`——所以正式部署把 exe 放在 `bin\cun\app\`、配置放 `bin\cun\` 即可自动找到；`dotnet run` 调试时也能向上定位到仓库里的配置。

## 🔬 工作原理

读取结算画面**顶部状态栏**的清晰字体：隔离白字的深色描边 → 用 Tesseract 识别 `SCORE / ATTACK / MISS`，
由得分换算评级（顶栏在某项为 0 时会隐藏该项，据此判 0）。大号彩虹分数/评级因字体花哨**不**直接 OCR。
OCR 结果缓存在 `cun_ocr_cache.json`，改区间后重新判定是**瞬间**完成的（无需重新识别）。

**DGHub 联动**不走 OCR：按 [Chuni2Api](https://github.com/iyxddw/Chuni2Api) 的方式在游戏进程内存里签名扫描
`NUM_jctirical` 等字段名定位四个判定计数地址（**只读**，不写内存、不注入），20Hz 轮询。
曲目结束时计数内存被释放（或原地清零），以此为结算信号，用最后一帧计数换算得分
（CHUNITHM 无连击加成：`得分 = 1,000,000/物量 × (1.01×JC + 1.0×JUSTICE + 0.5×ATTACK)`，与实际显示最多差 ±1），
再跑与截图分类相同的「寸」规则引擎得出是否「寸了」。

分工与 Chuni2Api 生态一致：**cun 只出数据**——在 `127.0.0.1:8890` 提供 SSE 流（`/events`：判定计数 +
带寸判定结果的 `settle` 事件；`/data`：快照）；**触发在 DGHub 插件里**——`dghub-plugin/` 是标准
DGHub 外部插件（由 DGHub 启动并传入 token，无需任何手动配置），订阅该流后按插件配置页里的
开关 / 强度 / 波形预设 / 通道发 `trigger`。

**自动截图**的触发是**判定数冻结**：结算画面显示期间计数块仍存活、冻结在最终值（内存要等玩家离开结算
画面才释放，等释放就晚了）——计数连续 2.5 秒不变即开始每 0.5 秒抓一帧游戏窗口（无边框窗口直接屏幕
拷贝），用**像素指纹**确认确实是结算画面：17 个在全部存量结算图上恒定不变的 UI 骨架像素点
（`tools/gen_result_signature.py` 从归档截图统计生成；打歌 / 地图画面只命中 9~11/17，阈值 16/17，
因此曲中长空档的误触发不会落盘）——命中后再等 `delay_s` 秒让分数滚完、复验一次才保存；判定数据
（得分 / ATTACK / MISS）直接写入 OCR 缓存，归档分类零 OCR。

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
├─ dghub-plugin/     # DGHub 外部插件（manifest.json + main.py；压 zip 后在 DGHub 导入）
├─ tools/            # gen_result_signature.py（从归档截图统计生成结算画面像素指纹）
├─ cun_config.json   # 种子配置（界面读写；发版时随包附带）
├─ 奶奶蛙.png         # 图标源图
├─ .github/workflows/ # build.yml（编译 CI）/ release.yml（tag 触发发版）
└─ LICENSE
```

各 `Services` 模块职责：`OcrService`（结算画面 OCR）、`ConfigService`（配置读写 / 路径解析 / 评级）、
`ClassifierService`（分类 / 复制 / 整理移动 / 扫描 / 缓存 / 每日统计）、`WatcherService`（游戏感知后台监视）、
`JudgeMemoryService`（游戏内存判定计数只读 + 曲终检测）、`LinkServerService`（本机 SSE 数据服务，供 DGHub 插件订阅）、
`AutostartService`（开机自启）、`NativeUtil`（进程检测 / IDLE 优先级 / 数据目录 / 深色标题栏）。

## ❓ FAQ

- **识别不到 / 全是空？** 确认是 1920×1080 截图、装了 Tesseract（且能找到 `eng.traineddata`），且截图目录指向正确。
- **提示找不到 OCR 引擎？** 装一下 Tesseract OCR，或把含 `eng.traineddata` 的 `tessdata` 放到 exe 同级 / 配好 `tesseract_cmd`。
- **开了整理后原图不见了？** 整理只把**识别到成绩**的结算截图**移动**到归档文件夹（如 `日期/评级/达成`），不是删除；在输出目录对应子文件夹里能找到，可手动移回。无法识别的图片（壁纸、其它截图）会留在原地不动。
- **会不会掉帧？** 识别只在结算画面、IDLE 优先级；或把 `process_mode` 设为 `on_close`，游戏中零识别。
- **DGHub 联动连不上？** 三步排查：① cun「运行」页联动状态是否「监听 …8890」；② DGHub 插件「启动检查」里 cun 数据服务是否 OK（不是就核对插件配置里的端点端口与 cun 一致）；③ 插件已在 DGHub 里启用。
- **联动会改游戏内存吗？** 不会。只用 `ReadProcessMemory` 读取判定计数，不写入、不注入、不 hook。
- **「接入 start.bat」改了什么？** 只在 `@echo off` 之后插入一行 `start "chunithm-cun-sorter" "<本程序路径>" --watch`（保留原有各行内容与编码，换行统一为批处理标准的 CRLF——cmd 对纯 LF 的 bat 会吞掉行首字符），并在同目录留一份 `.cun-backup` 备份；取消勾选即精确移除该行。程序若已在运行则不会重复启动（单实例）。

## 📝 更新记录

### v1.3（2026-07-01）
- 📸 **新增自动截图**：曲终后自动截取结算画面存入截图目录（像素指纹识别 + 等分数滚完再存），判定数据直接取自内存写入缓存——**新截图零 OCR**，外部截图工具可下岗；指纹由 `tools/gen_result_signature.py` 从存量归档统计生成（229/229 全中、打歌画面 9/17 不误报）。
- ⚡ **新增 DGHub 联动**：从游戏内存只读判定计数（签名扫描，移植自 [Chuni2Api](https://github.com/iyxddw/Chuni2Api)），打歌中 **MISS / ATTACK** 实时触发波形，**结算时按你的「寸」判定规则**（得分由判定数精确换算）命中即触发。
- 🔌 配套 **DGHub 外部插件** `dghub-plugin/`（Release 附 `cun_dghub_plugin_*.zip`，DGHub「导入 zip 包」安装）：触发开关 / 强度 / 波形预设（自动拉取 DGHub 预设列表）/ 通道 / 持续时长全部在 **DGHub 插件配置页**调节，支持「启动检查」；cun 侧在 `127.0.0.1:8890` 提供 SSE 数据服务（判定流 + 结算寸判定事件）。
- 🖥️ 「配置」页新增 **DGHub 联动**开关与数据端口；「运行」页新增联动状态，结算记录进「最近命中」日志。
- 🚀 **新增「接入 start.bat」**（「运行」页）：一键向游戏 `start.bat` 注入自启动行，开游戏即自动启动本程序、开始监视并缩到托盘；原文件备份 `.cun-backup`、保留原编码与换行、取消勾选精确还原；程序改为**单实例**（重复启动自动退出）。
- 🐛 **修复：窗口隐藏在托盘时，右键菜单点了没反应**——托盘菜单改用独立窗口承载（H.NotifyIcon `SecondWindow` 模式），「显示主界面 / 退出」在任何状态下都能点；另外**双击托盘图标**也可直接显示主界面。
- 🐛 **修复：开启「达成」整理后 AJ / FC 原图不再被扫描统计**——归档到根 `AJ\`、`FC\` 的原图曾被当作旧版工具副本整树跳过（v1.2 起的潜在问题，「达成」排最外层时触发）；现在这两个目录下只跳过带 `__` 标记的副本，原图照常扫描。
- 📄 `cun_config.json` 新增 `dghub` 配置节（`enabled` / `port`）与 `start_bat`；发版流程随包产出插件 zip。

### v1.2.1（2026-06-25）
- 🛡️ **整理更安全**：只移动**识别到成绩**的结算截图；目录里的壁纸 / 其它图片、以及识别失败的图**留在原地不动**（不再被扫进 `未知日期` / `未知评级` 之类文件夹）。
- 🧹 **不再误删空目录**：整理后只清理**因移动而腾空**的源文件夹，不再递归删除输出目录下任意空文件夹。
- 🔁 **关闭整理后统计一致**：扫描始终递归查找原图（排除工具自己的 `寸/AJ/FC` 副本），已归档到子文件夹的截图照样被扫描与统计。
- ⬆️ **升级不丢规则**：从 v1.1 升级时只丢弃旧的**内置预设**，你**手动添加 / 改过**的判定规则会保留。
- 🧯 **修复若干崩溃 / 一致性问题**：选目录 / 添加规则对话框异常不再导致闪退；提示条不再被上一条的计时器提前关掉；OCR 缓存按文件大小校验，避免同名不同文件「串味」；重建扫描会**递归**清理嵌套的旧 `寸/…`、`FC/` 副本；避免重复生成 `(N)` 副本。
- ⚡ **更省资源**：后台监视不再每 ~2 秒整文件重读配置（按修改时间缓存）；统计图表在窗口缩放时合并重绘。
- 🧱 内部重构：AJ / FC 判定统一为单一来源；评级档位分数区间下沉到 `ConfigService` 共用。

### v1.2（2026-06-06）
- 🗂️ 新增**整理归档**：按 日期 / 评级 / 达成（AJ·FC）把原图移动归档，维度可拖动 / ↑↓ 排序、自由嵌套。
- 🎯 判定规则改为**完全自定义**：内置预设改由「添加判定规则」对话框按需创建，`categories` 初始为空。
- 🖼️ 新增**深色标题栏**与切换页面的淡入过渡动画；统计新增 **FC** 曲线。
- 🗃️ 新增「目录设置」界面（截图目录 / 输出目录可视化选择）。

## 🙏 致谢

- [Windows App SDK / WinUI 3](https://learn.microsoft.com/windows/apps/winui/winui3/) · [H.NotifyIcon](https://github.com/HavenDV/H.NotifyIcon) · [Tesseract .NET](https://github.com/charlesw/tesseract)
- OCR 引擎：[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

## 📄 许可

[MIT](LICENSE)。本项目为非官方同人工具，与 SEGA 无关；CHUNITHM 及相关素材归 SEGA 所有。
