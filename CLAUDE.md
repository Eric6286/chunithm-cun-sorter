# CLAUDE.md

Claude 在本仓库（今天你寸了吗 / chunithm-cun-sorter）工作时的约定与速查。
人看的现状和用法在 [README.md](README.md)。

## 约定（必须遵守）

- **README 同步**：每次做了功能 / 行为 / 配置项 / 命令 / 版本上的改动，都要在**同一次改动**里
  更新 `README.md` 的相应小节（功能特性、界面说明、判定与整理、`cun_config.json` 配置表、
  版本号、FAQ 等），并在 [更新记录.md](更新记录.md) 里补一条带日期和版本号的条目。
- **版本号只有一处真源**：`core/version.py` 的 `__version__`。exe 的版本资源、安装包文件名、
  控制面板里的卸载项版本全从那里读，别在别处再写一份。
- 发版时一并更新 README 里的版本号与安装包文件名。

## 这是什么

CHUNITHM「寸」成绩识别 + 截图归档 + DGHub 联动。**PySide6 桌面程序**，托盘常驻，
PyInstaller + Inno Setup 出安装包。

v2.0 之前是 WinUI 3 / .NET 8（`CunSorter/`），已整体删除；再往前 v1.0 是 Python + qfluentwidgets。
要看旧实现去 git 历史。

## 架构

方向单向，`core/` 不 import `ui/`：

```
main.py            界面入口（--watch 随游戏启动）    cli.py   命令行入口
   ↓                                                    ↓
ui/main_window.py  主窗口：导航 + 三页 + 托盘 + 服务生命周期
   ↓ 用
ui/page_config.py / page_stats.py / page_run.py / first_run.py / rule_dialog.py
   ↓ 都用
ui/theme.py        配色 / 字号 / 样式表        ui/widgets.py  开关、卡片、曲线、浮条
   ↓
core/classifier.py 判定 / 复制 / 整理 / 扫描 / 缓存 / 统计   ←── 两个前端共用
   ↓ 用
core/ocr.py        结算截图 OCR（子进程调 tesseract）
core/config.py     配置读写 / 迁移 / 路径推导      core/models.py  数据结构
core/watcher.py    目录监视 + 游戏感知
core/judge_memory.py  内存签名扫描（只读）
core/link_server.py   本机 SSE 数据服务（DGHub 插件连它）
core/capture.py       结算画面自动截图 + 像素指纹
core/start_bat.py  start.bat 注入      core/autostart.py  开机自启
core/game_locator.py  自动找游戏目录    core/paths.py  数据目录定位
core/winapi.py     ctypes 封装：进程 / 窗口 / 抓帧 / 单实例 / DPI
```

**`ui/__init__.py` 和 `core/__init__.py` 都不做急切导入。** 在那里 re-export 会让
`import core.config` 这种轻量用途把 PySide6 一起拉起来，命令行和测试就跑不了了。

## 不许破坏的不变量

1. **得分换算必须走整数、必须截断。**（`core/models.py` 的 `JudgeCounts.score`）
   游戏显示的是截断值：150 张真实截图上截断值 149 次完全吻合，四舍五入会高 1 分。
   而截断又必须用整数运算。浮点会把本该整除的值算成 `1009989.999…`，再截断就少 1，
   实测有 48 组判定数会踩到，其中 129 物量全 JC 会被算成 1,009,999 而不是满分。
   → 测试 `test_the_score_truncates_instead_of_rounding`、
   `test_an_all_justice_run_is_exactly_full_marks_even_at_awkward_note_counts`
2. **判定命中只复制，整理才移动，而且只移动识别出成绩的图。**
   壁纸和识别失败的图片永远留在原地。→ `test_an_unrecognised_shot_is_never_moved`
3. **扫描按位置排除工具自己的副本**（`寸/` 及各规则目录），不是按文件名里有没有 `__`。
   用户截图里碰巧带 `__` 不能被误伤。而 `AJ/` `FC/` 兼作整理目的地，那两个目录下
   才用 `__` 标记区分。→ `test_our_own_copies_are_excluded_by_location`
4. **顶栏那一行 OCR 前要补留白，得分那一行不能补。**
   数字紧贴右边界时 tesseract 会把边缘噪点连上去（实测「MISS : 1」读成「14」，7 张真实
   截图上都是）。但同样的留白加在得分行上，psm 7 会整行读空，303 张真实截图上多出
   115 处得分错误。→ `core/ocr.py` 的 `TOP_LINE_PAD`
5. **成绩画面识别要两道检查叠加**：17 点像素指纹 + 判定明细面板均色。
   曲终先出现的 CLEAR 过场和成绩画面共享**全部**顶部 chrome，单靠指纹分不开，
   生产环境就是这么截错的。→ `test_the_chrome_alone_is_not_enough_to_be_a_result_screen`
6. **内存读取只读。** `ReadProcessMemory` / `VirtualQueryEx`，不写、不注入、不 hook。
7. **后台线程的回调一律通过 Qt 信号回界面线程。** 直接从工作线程碰部件是未定义行为。

## 会浪费半小时的坑

- **ctypes 的句柄参数必须写 `argtypes`/`restype`。** 默认按 `c_int` 传，64 位下
  `HANDLE`/`HWND`/`HDC` 被截成低 32 位，表现是「调用失败但错误码看着正常」。
  `core/winapi.py` 里 `_declare()` 集中写死了所有签名，加新 API 要一起加。
- **QSS 里绝不要写 `QWidget { background: ... }`。** Qt 的类型选择器连子类一起命中，
  每个 QLabel 都会被刷上底色，在卡片上显示成一条条横杠。背景只画在容器上，
  用 objectName 选择器。
- **字体要用 `QFont.setFamilies(整条字体栈)`**，不要「挑第一个装了的家族」。
  Segoe UI 没有汉字字形，选中它之后中文走系统兜底、行高对不齐。
- **`QFontDatabase.families()` 在 offscreen 平台返回空列表**，所以离屏截图里中文全是豆腐块。
  那是平台的事，不是代码的问题，别去追。
- **`_ocr()` 不负责关 PIL 图像**：第二行可能要换个 psm 再喂一次，提前关掉就 `ValueError:
  Operation on closed image`。生命周期由 `detect()` 管。
- **别在仓库根放 `cun_config.json`。** 源码运行时 `portable_dir()` 会往上找到它，
  整个程序误判成便携部署，截图目录被推到仓库旁边去。`_fill_paths` 里有一道守卫，别拿掉。
- **`installer.iss` 必须存成 UTF-8 with BOM**，否则 ISCC 按 ANSI 读，中文全是乱码。

## 数据落在哪

| | 位置 |
|---|---|
| 程序 | `%LOCALAPPDATA%\Programs\今天你寸了吗\`（安装器默认，装到用户目录不弹 UAC） |
| 配置 / 缓存 / 日志 / 诊断图 | `%LOCALAPPDATA%\ChunithmCunSorter\` |
| 游戏目录 | 记在配置的 `game_root`，安装向导或首次运行向导里选 |

两个例外：环境变量 `CUN_DATA_DIR` 优先于一切（测试用）；exe 同级或任一上级目录里有
`cun_config.json` 就是**便携模式**，数据落那儿（v1.x 装在 `bin\cun\` 的老部署靠这条原地升级）。

## 命令

```powershell
.venv\Scripts\python -m pytest tests -q          # 测试
.venv\Scripts\python main.py                     # 跑界面
.venv\Scripts\python cli.py config               # 看当前配置
.venv\Scripts\python cli.py scan --rebuild       # 全量重扫
.venv\Scripts\python packaging\build.py          # 测试→exe→冒烟→安装包
```

**发版**：推送 `v*` tag → `.github/workflows/release.yml` 在 Windows runner 上打包并发布
GitHub Release（安装包 + DGHub 插件 zip）。

## 相关项目

- **DGHub 插件**在 `dghub-plugin/`，发版自动打 zip。它通过 `http://127.0.0.1:8890/events`
  读 SSE，用 `urllib.request.urlopen` 逐行读。改 `core/link_server.py` 的响应格式前先看它。
- **ChuniOptionManager** 共用一套 WinUI 约定，但那个项目**还没**做这次的解耦，
  仍然必须留在 `option` 目录里。
