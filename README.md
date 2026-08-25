<div align="center">

<img src="奶奶蛙.png" width="120" alt="奶奶蛙">

# 今天你寸了吗

CHUNITHM「寸」成绩自动识别 · 全截图归档 · DGHub 联动
*Near-miss detection, screenshot archiving and DGHub haptics for CHUNITHM. WinUI 3 / Fluent 2 / Mica.*

</div>

---

一个常驻托盘的 CHUNITHM 小工具，围绕「结算成绩」做三件事：

1. 识别与统计「寸」：按你自定义的判定规则（SSS寸 / AJ寸 / ATTACK+MISS…）把差一点的成绩**复制**到独立文件夹，并画出每日 寸 / AJ / FC 曲线；
2. 归档所有截图：按日期 / 评级 / 达成（AJ·FC）三个维度自动整理，维度可拖动排序、自由嵌套；
3. DGHub 联动 + 自动截图（可选）：从游戏内存**只读**判定计数，打歌中 MISS / ATTACK 实时触发 DGHub 波形、结算「寸了」触发；结算画面由本程序自动截图入库，新截图完全不需要 OCR。

成绩数据有两条来路，可以混用：

| | 截图 + OCR（传统路径） | 游戏内存（联动路径，v1.3 新增） |
|---|---|---|
| 数据来源 | 读结算截图顶栏的 SCORE / ATTACK / MISS | 签名扫描判定计数，得分由判定数精确换算 |
| 截图来源 | 外部截图工具 / 手动 | **本程序曲终自动截取** |
| 依赖 | Tesseract OCR | 无（也不需要 Python） |
| 用途 | 历史截图重扫、不开联动时的日常 | 实时触发 + 新截图零 OCR 归档 |

> 「寸」判定**只复制原图**；「整理」开启后，识别到成绩的结算截图会被**移动**到归档文件夹（只移动、不删除，可还原）；无法识别的图片（壁纸等）留在原地不动。识别在结算画面之后进行、以最低 CPU 优先级运行，不影响游戏帧数。内存读取仅 `ReadProcessMemory` **只读**，不写内存、不注入、不 hook。

> WinUI 3 + .NET 8（Windows App SDK）开发，自包含构建免装 .NET / Python。最新版本：[Release v1.3](https://github.com/ErikaAlk/chunithm-cun-sorter/releases/latest)。

## 功能特性

- 自定义判定规则（「寸」统计）：评级判定（SSS+寸 / SSS寸 / SS+寸 / SS寸 预设，下限可调，也可自定义区间）、AJ寸、ATTACK+MISS；每条可增删、可开关
- 整理归档（可选）：按日期（年/月/日）、评级、达成（AJ/FC/普通）归档；拖动或 ↑↓ 调顺序决定文件夹嵌套，靠上＝外层；只移动识别到成绩的原图，无关图片不动
- DGHub 联动（可选）：内存判定计数（签名扫描，移植自 [Chuni2Api](https://github.com/iyxddw/Chuni2Api)）+ 配套 DGHub 外部插件（Release 附 zip，导入即用）。打歌中 MISS / ATTACK 实时触发波形，结算按你的寸规则判定、寸了触发；强度 / 时长 / 波形预设 / 通道全在 DGHub 插件配置页调
- 自动截图（可选）：判定数冻结（= 进入结算画面）即开始像素指纹识别，等分数滚完自动截取结算画面存入截图目录；判定数据直接取自内存写入缓存，新截图零 OCR，外部截图工具可下岗
- 接入 start.bat（可选）：一键向游戏 `start.bat` 注入自启动行，开游戏时本程序自动启动、开始监视并缩到托盘（原文件备份 `.cun-backup`，取消勾选精确还原；单实例不重复启动）
- 每日 寸 / AJ / FC 数量曲线 + 统计卡片（今天 / 近 7 天 / 累计 / 最高一天）
- Fluent 2 设计 + Win11 Mica + 深色标题栏；托盘常驻（双击图标显示主界面）、可开机自启
- 低占用：IDLE 优先级、OCR 结果缓存、可选「关游戏后再处理」模式；自包含发布

## 运行要求

- Windows 10 1809+ / 11，x64；游戏窗口 / 截图分辨率 1920×1080 最稳（其它分辨率按比例缩放）
- Tesseract OCR（<https://github.com/UB-Mannheim/tesseract/wiki>）：走截图 + OCR 这条路时必需。装到默认路径 `C:\Program Files\Tesseract-OCR\` 即可，或把含 `eng.traineddata` 的 `tessdata` 放 exe 同级 / 在配置里改 `tesseract_cmd`。只用联动 + 自动截图的话，新成绩不需要它，历史截图重扫仍需要
- DGHub 主程序（<http://www.dghub.top/>）：只有开 DGHub 联动才要。DG-Lab 郊狼设备的联动主程序，从其「插件中心 → 外部插件」导入本项目的联动插件
- *（仅从源码构建时）* **.NET 8 SDK**

## 快速开始

### 基础使用（识别 + 归档）
1. 下载最新 `chunithm-cun-sorter_v1.3_win64.zip`，解压得到 `cun` 文件夹，放到 `<CHUNITHM>\bin\`（与 `screenshots` 同级，最终为 `<CHUNITHM>\bin\cun\`）。
2. 双击 **`app\今天你寸了吗.exe`** 启动。
3. 「配置」页设好截图目录、添加判定规则、按需开启整理，保存；点「应用并重新扫描」可整理历史截图。
4. 想随游戏自动启动：「运行」页勾选「接入 start.bat」，选中游戏的 `start.bat` 即可，以后开游戏就全自动。

> 截图目录默认自动取 `<安装目录上级>\screenshots`；不在那儿就在「配置 → 目录设置」浏览指定。

### DGHub 联动 + 自动截图（可选）
> 需要先安装 **DGHub 主程序**（<http://www.dghub.top/>）并连好 DG-Lab 设备；波形预设也在 DGHub 里管理。
1. 下载 Release 里的 `cun_dghub_plugin_v1.3.zip`，在 DGHub「插件中心 → 外部插件 → 导入 zip 包」安装「今天你寸了吗 · 联动」并启用；触发开关 / 强度 / 波形预设（自动列出 DGHub 预设）/ 通道都在其插件配置页调，「启动检查」可看连接状态。
2. cun 的「配置 → DGHub 联动」打开开关（默认端口 8890），「配置 → 自动截图」按需打开，保存立即生效。
3. 开打。打歌中吃 MISS 即触发；每首歌结算自动截图、按寸规则判定并归档，全程零 OCR。

### 从源码构建
```powershell
dotnet build CunSorter/CunSorter.csproj -c Release          # 构建
dotnet run --project CunSorter -c Release                   # 运行
# 打包自包含文件夹：
dotnet publish CunSorter/CunSorter.csproj -c Release -r win-x64 --self-contained `
  -p:Platform=x64 -p:WindowsAppSDKSelfContained=true -o publish_out
```
把 `publish_out` 内容放进 `<CHUNITHM>\bin\cun\app\`，上级 `cun\` 放一份 `cun_config.json`。

> **发版**：推送 `v*` tag（如 `git tag v1.3 && git push origin v1.3`），`release.yml` 会在 Windows runner 上自动构建主程序包与 DGHub 插件 zip 并发布 GitHub Release。

## 界面说明（三页）

- 配置
  - 目录设置：截图目录（要扫描的原图）/ 输出目录（分类结果根目录）。
  - 判定规则（寸）：点「添加判定规则」→ 选评级判定 / AJ寸 / ATTACK+MISS；命中的图**复制**到 `寸/` 下并计入统计。
  - 整理：日期 / 评级 / 达成三行各自开关，拖动或 ↑↓ 排序决定嵌套层级；开启任一项后扫描会**移动**原图归档。
  - DGHub 联动：总开关 + 本机数据端口（默认 8890）；触发参数在 DGHub 插件配置页调。
  - 自动截图（结算画面）：开关 + 「等 N 秒再保存」（等结算分数滚完，默认 2.5）；本开关或联动任一开启即运行内存读取。
  - `保存配置`（所有开关立即生效）/ `应用并重新扫描` / `打开输出文件夹`。
- 统计：每日 寸 / AJ / FC 曲线 + 今天 / 近 7 天 / 累计 / 最高一天。
- 运行：`realtime` / `on_close` 模式切换、启停监视、游戏状态、联动状态（数据服务 / 判定读取）、接入 start.bat、开机自启；「最近命中」实时滚动寸命中、结算与截图记录。
  监视运行时关窗口＝**最小化到托盘**继续后台监视（右键托盘菜单显示主界面 / 退出，双击图标直接显示）。

## 判定与整理

### 判定规则（「寸」统计，复制原图）
| 类型 | 判定 | 说明 |
|---|---|---|
| 评级判定 | `下限 ≤ 得分 ≤ 上限` | 预设档位 `SSS+寸 / SSS寸 / SS+寸 / SS寸`（下限可改、上限固定），或自定义区间 |
| AJ寸 | `ATTACK=0 且 0<MISS≤x` | 差一点 AJ |
| ATTACK+MISS | `ATTACK≤a 且 MISS≤m 且 A+M>0，评级≥门槛` | |

> 评价分数段：SSS+ `≥1,009,000`、SSS `≥1,007,500`、SS+ `≥1,005,000`、SS `≥1,000,000` …（满分 1,010,000）。
> 一张图可同时命中多条规则，分别复制到各自子文件夹，文件名标注类别与成绩，如 `2026-05-29_08-18-04__SSS寸_SSS_A2M0_1008792.png`。

### 整理维度（移动原图）
| 维度 | 生成文件夹 |
|---|---|
| 日期 | `2026` / `2026-05` / `2026-05-24`（按年 / 月 / 日） |
| 评级 | `SSS+` / `SSS` / `SS+` / … |
| 达成 | `AJ`（A0 M0）/ `FC`（无 MISS）/ `普通` |

> 顺序决定嵌套：「日期」在上、「评级」在下 → `2026-05/SSS+/图.png`。AJ / FC 属于整理维度，不计入「寸」。
> 某维度取不到值会跳过该层，不建「未知」文件夹；关掉整理后已归档的截图仍会被扫描统计。

## 配置 `cun_config.json`

| 键 | 说明 |
|---|---|
| `screenshots_dir` | 监视的截图目录（留空自动取 `<安装目录上级>\screenshots`） |
| `output_root` | 输出根目录（留空同 `screenshots_dir`） |
| `tesseract_cmd` | Tesseract 路径（OCR 路径用；留空 / 找不到回退 PATH） |
| `process_mode` | `realtime`（实时·低优先级）或 `on_close`（关游戏后处理） |
| `game_process` | 游戏进程名（默认 `chusanApp.exe`） |
| `rename_with_stats` | 复制时在文件名追加成绩与类别 |
| `rank_thresholds` | 各评级分数线 |
| `categories[]` | 自定义判定规则（界面增删） |
| `organize.steps[]` | 整理维度与顺序（`date` / `rank` / `achievement`，列表序＝嵌套序） |
| `boxes` / `dark_threshold` / `bright_threshold` | OCR 区域与阈值（基于 1920×1080） |
| `start_bat` | 已接入的游戏 `start.bat` 路径（「运行」页管理，是否接入以 bat 内容为准） |
| `dghub.enabled` / `dghub.port` | DGHub 联动开关 / 本机数据端口（默认 `8890`；触发参数在 DGHub 插件配置页） |
| `capture.enabled` | 自动截图开关（默认 `false`） |
| `capture.delay_s` / `capture.timeout_s` | 识别到结算画面后等几秒再存（默认 2.5）/ 单次尝试最长等待（默认 30） |

> 数据目录定位：程序从 exe 所在目录逐级向上找 `cun_config.json`。部署时 exe 放 `bin\cun\app\`、配置放 `bin\cun\` 即自动找到；`dotnet run` 调试也能向上定位到仓库配置。

## 工作原理

OCR 路径：读结算画面顶部状态栏的清晰字体，隔离白字深色描边 → Tesseract 识别 `SCORE / ATTACK / MISS`，
由得分换算评级（顶栏某项为 0 时隐藏，据此判 0）。结果缓存于 `cun_ocr_cache.json`（按文件名 + 大小校验），
改规则重判**瞬间**完成、无需重新识别。

内存路径：按 [Chuni2Api](https://github.com/iyxddw/Chuni2Api) 的方式在游戏进程里签名扫描 `NUM_jctirical`
等字段名定位四个判定计数地址（**只读**，20Hz 轮询）。CHUNITHM 无连击加成，得分可由判定数精确换算：
`得分 = 1,000,000/物量 × (1.01×JC + 1.0×JUSTICE + 0.5×ATTACK)`（与显示分最多差 ±1）；评级、AJ/FC、
寸判定全部由此推出，**不需要**再逆向其它字段。

DGHub 联动采用与 Chuni2Api 一致的分工：cun 在 `127.0.0.1:8890` 提供 SSE 数据流（`/events`：判定计数 +
带寸判定结果的 `settle` 事件；`/data`：快照）；触发在 DGHub 外部插件（`dghub-plugin/`）里完成，由 DGHub
启动并传 token、零手动接线，按插件配置页的参数发 `trigger`。

自动截图的触发是判定数冻结：结算画面显示期间计数块仍存活、冻结在最终值（内存要到玩家离开结算画面
才释放，等释放就晚了）。计数连续 2.5 秒不变即开始每 0.5 秒抓帧（无边框窗口直接屏幕拷贝），用像素指纹
确认是成绩画面（双重校验）：① 17 个在全部存量成绩图上恒定不变的 UI 骨架像素点（`tools/gen_result_signature.py`
从归档统计生成；打歌 / 地图画面只命中 9~11/17，阈值 16/17）。但曲终先出现的 CLEAR 过场与成绩画面共享
全部顶部 chrome，单靠它分不开；所以再加 ② 判定明细面板区域均色（成绩画面中部的深紫色面板，CLEAR 那里是
近白背景，偏差 ≥90）。两者都命中后等 `delay_s` 让分数滚完、复验一次才保存；判定数据直接写入缓存，归档分类零 OCR。

## 目录结构

```
.
├─ CunSorter.sln
├─ CunSorter/
│  ├─ CunSorter.csproj
│  ├─ App.xaml(.cs) / MainWindow.xaml(.cs)
│  ├─ Models/        # CunConfig / Category / OrganizeConfig / OcrResult
│  ├─ Services/      # OCR / 配置 / 分类·整理·扫描 / 监视 / 内存判定 / 联动服务 / 截图 / start.bat / 自启 / 原生工具
│  ├─ Pages/         # 配置 / 统计 / 运行 三页
│  └─ Assets/        # icon.ico / 奶奶蛙.png
├─ dghub-plugin/     # DGHub 外部插件（manifest.json + main.py；发版自动打 zip）
├─ tools/            # gen_result_signature.py（从归档截图统计生成结算画面像素指纹）
├─ cun_config.json   # 种子配置（界面读写；发版随包附带）
├─ 奶奶蛙.png         # 图标源图
├─ .github/workflows/ # build.yml（编译 CI）/ release.yml（tag 触发发版）
└─ LICENSE
```

各 `Services` 模块：`OcrService`（结算画面 OCR）、`ConfigService`（配置 / 路径 / 评级）、`ClassifierService`
（分类 / 复制 / 整理 / 扫描 / 缓存 / 统计）、`WatcherService`（游戏感知监视 + 缓存种子）、`JudgeMemoryService`
（内存判定只读 + 曲终检测）、`LinkServerService`（本机 SSE 数据服务）、`CaptureService`（结算画面自动截图）、
`StartBatService`（start.bat 注入）、`AutostartService`（开机自启）、`NativeUtil`（进程 / 优先级 / 数据目录等）。

## FAQ

- 识别不到 / 全是空？确认是 1920×1080 截图、装了 Tesseract（能找到 `eng.traineddata`）、截图目录正确。
- DGHub 联动连不上？① cun「运行」页联动状态是否「监听 …8890」；② DGHub 插件「启动检查」里 cun 数据服务是否 OK（核对端点端口一致）；③ 插件已启用。
- 自动截图偶尔提示「超时；最高指纹得分 9/17」？曲中长空档的良性误触发，指纹已正确拦截，不影响任何东西；真正的结算画面得分是 17/17。
- 联动会改游戏内存吗？不会。只读判定计数，不写入、不注入、不 hook。
- 「接入 start.bat」改了什么？在 `@echo off` 后插入一行 `start "chunithm-cun-sorter" "<本程序路径>" --watch`（保留原内容与编码，换行统一 CRLF，cmd 对纯 LF 的 bat 会吞行首字符），并留 `.cun-backup` 备份；取消勾选精确移除。已在运行则不重复启动。
- 开了整理后原图不见了？只是**移动**到了归档文件夹（如 `日期/评级/达成`），没有删除，可手动移回。
- 会不会掉帧？识别在结算后、IDLE 优先级；截图抓帧只在计数冻结（结算 / 长空档）期间发生。

## 更新记录

### 未发布（2026-08-25）

- README 和「配置」页那段自动截图说明重写了一遍：标题和列表项前面的 emoji、
  满屏加粗、破折号都去掉了，内容一条没删。更新记录里各版本的条目只去掉 emoji 和加粗。
- 两处链接还指着废弃的 Eric6286 账号（README 的 Release 链接、release.yml 的发版说明），
  改成 ErikaAlk。
- 没有出新包，也没有新 tag。

### v1.3（2026-07-04）
- 新增 DGHub 联动：内存只读判定计数（签名扫描，移植自 [Chuni2Api](https://github.com/iyxddw/Chuni2Api)），打歌中 MISS / ATTACK 实时触发波形，结算按寸规则判定（得分由判定数精确换算）命中即触发。
- 配套 DGHub 外部插件（Release 附 `cun_dghub_plugin_*.zip`，导入即用）：触发开关 / 强度 / 波形预设 / 通道全在 DGHub 插件配置页，支持「启动检查」；cun 在本机 8890 提供 SSE 数据服务。
- 新增自动截图：判定数冻结（进入结算）即开始识别，等分数滚完自动截取成绩画面；判定数据直接入缓存，新截图零 OCR。成绩画面识别用双重校验：17 点 UI 骨架像素指纹（排除打歌 / 地图画面）+ 判定明细面板区域均色（排除曲终先出现、共享同款顶栏的 CLEAR 过场）；指纹由 `tools/gen_result_signature.py` 从存量归档统计生成，实机验证连续多首命中成绩图、不误截过场。
- 新增「接入 start.bat」：一键注入自启动行，开游戏自动启动并开始监视（备份 / 可还原 / 单实例）。
- 修复：窗口隐藏在托盘时右键菜单点了没反应（改用独立窗口承载菜单，另加双击图标显示主界面）；开启「达成」整理后归档到根 `AJ\`、`FC\` 的原图不再被扫描统计的问题（现只跳过带 `__` 标记的工具副本）。
- 「配置」页新增 DGHub 联动 / 自动截图设置区；「运行」页新增联动状态与 start.bat 接入；结算与截图记录进「最近命中」与 `cun.log`。
- `cun_config.json` 新增 `dghub` / `capture` / `start_bat` 配置。

### v1.2.1（2026-06-25）
- 整理更安全：只移动识别到成绩的结算截图；壁纸 / 识别失败的图留在原地。
- 不再误删空目录：只清理因移动而腾空的源文件夹。
- 关闭整理后统计一致：扫描始终递归查找原图（排除工具自己的副本）。
- 升级不丢规则：只丢弃旧内置预设，手动添加 / 改过的规则保留。
- 修复若干崩溃 / 一致性问题；更省资源；内部重构（AJ/FC 判定单一来源等）。

### v1.2（2026-06-06）
- 新增整理归档（日期 / 评级 / 达成，可拖动排序嵌套）。
- 判定规则改为完全自定义；深色标题栏与页面过渡动画；统计新增 FC 曲线；「目录设置」界面。

## 致谢

- [Chuni2Api](https://github.com/iyxddw/Chuni2Api)（内存签名扫描方案）· [DGHub](http://www.dghub.top/)（外部插件协议）
- [Windows App SDK / WinUI 3](https://learn.microsoft.com/windows/apps/winui/winui3/) · [H.NotifyIcon](https://github.com/HavenDV/H.NotifyIcon) · [Tesseract .NET](https://github.com/charlesw/tesseract) · [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

## 许可

[MIT](LICENSE)。本项目为非官方同人工具，与 SEGA 无关；CHUNITHM 及相关素材归 SEGA 所有。
