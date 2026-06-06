<div align="center">

<img src="CunSorter/Assets/奶奶蛙.png" width="120" alt="奶奶蛙">

# 今天你寸了吗 · WinUI 3 版

**CHUNITHM「寸」成绩自动识别与归档工具 —— WinUI 3 / .NET 8 移植版**

</div>

---

这是把原 Python（PySide6 + qfluentwidgets）工具用 **WinUI 3 + C# / .NET 8** 重写的版本。
功能、配置文件、归类规则与原版**完全一致**，并且**共用同一个 `cun_config.json` 与
`cun_ocr_cache.json`**，可以和 Python 版互换使用。

> 原 Python 代码仍保留在仓库根目录，作为对照与回退。

## ✨ 与原版对应关系

| 功能 | Python 文件 | WinUI 3 文件 |
|---|---|---|
| 结算画面 OCR | `cun_detect.py` | `Services/OcrService.cs` |
| 配置读写 / 路径解析 / 评级 | `cun_detect.py` | `Services/ConfigService.cs` |
| 分类 / 复制 / 扫描 / 缓存 / 统计 | `cun_core.py` | `Services/ClassifierService.cs` |
| 游戏感知监视器 | `cun_core.py`（Watcher） | `Services/WatcherService.cs` |
| 进程检测 / IDLE 优先级 / 数据目录 | `cun_core.py` / `cun_detect.py` | `Services/NativeUtil.cs` |
| 开机自启 | `cun_gui.py` | `Services/AutostartService.cs` |
| 主窗口 + Mica + 托盘 | `cun_gui.py` | `MainWindow.xaml(.cs)` |
| 规则设置页 | `ConfigInterface` | `Pages/ConfigPage.xaml(.cs)` |
| 统计页（曲线图） | `StatsInterface`（QtCharts） | `Pages/StatsPage.xaml(.cs)`（Canvas 手绘） |
| 运行 / 监视页 | `RunInterface` | `Pages/RunPage.xaml(.cs)` |

界面用 **Fluent 2 NavigationView + Win11 Mica 背景**，每日「寸」曲线（含 AJ 线）用
`Canvas` 手绘，系统托盘用 [H.NotifyIcon.WinUI](https://github.com/HavenDV/H.NotifyIcon)。

## 🧩 运行 / 构建要求

- **Windows 10 1809+ / 11**
- **.NET 8 SDK**：<https://dotnet.microsoft.com/download>
- **Visual Studio 2022**（含「.NET 桌面开发」+「Windows App SDK C# 模板」）或仅命令行 SDK
- **Tesseract OCR 的 `tessdata`**：本移植用 [Tesseract .NET](https://www.nuget.org/packages/Tesseract)
  引擎，需要 `eng.traineddata`。两种获取方式：
  1. 已装系统版 Tesseract（默认 `C:\Program Files\Tesseract-OCR\`）—— 程序会自动用其
     `tessdata` 目录；
  2. 或把含 `eng.traineddata` 的 `tessdata` 文件夹放到 exe 同级目录。
- 截图分辨率 **1920×1080** 最稳（其它分辨率按比例自动缩放识别区域）

## 🚀 构建与运行

```powershell
cd winui3
dotnet restore
dotnet build -c Release

# 直接运行（开发）
dotnet run --project CunSorter -c Release
```

### 打包为独立文件夹（免装 .NET 运行时）

```powershell
cd winui3
dotnet publish CunSorter -c Release -r win-x64 --self-contained `
  -p:WindowsAppSDKSelfContained=true -p:Platform=x64
```

产物在 `CunSorter\bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish\`，
把整个 `publish` 文件夹放到 **`<CHUNITHM>\bin\cun\app`**（与原版同样的部署方式）即可，
程序会自动在上级目录找到 `screenshots` 与 `cun_config.json`。

> **数据目录定位（务必按部署方式来）**：`NativeUtil.DataDir()` 与 Python 的
> `data_dir()` 一致 —— 先看 **exe 同级**有没有 `cun_config.json`，没有再看**上一级**。
> 所以正式用法是把 publish 放进 `bin\cun\app\`，让程序在上级 `bin\cun\` 找到配置与缓存。
>
> 如果你只是 `dotnet run` 或直接在 `bin\<...>\publish\` 原地启动、而**上级目录没有
> `cun_config.json`**，程序会**回退到默认配置**（screenshots/output 指向默认推断路径）。
> 想原地测试，最简单的办法是把一份 `cun_config.json` 复制到 **exe 同级目录**即可。

## 📁 目录结构

```
winui3/
├─ CunSorter.sln
└─ CunSorter/
   ├─ CunSorter.csproj
   ├─ app.manifest
   ├─ App.xaml(.cs)
   ├─ MainWindow.xaml(.cs)
   ├─ Models/         # CunConfig / Category / OcrResult
   ├─ Services/       # OCR / 配置 / 分类 / 监视 / 自启 / 原生工具
   ├─ Pages/          # 配置 / 统计 / 运行 三页
   └─ Assets/         # icon.ico / 奶奶蛙.png
```

## 📄 许可

[MIT](../LICENSE)。本项目为非官方同人工具，与 SEGA 无关；CHUNITHM 及相关素材归 SEGA 所有。
