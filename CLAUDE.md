# CLAUDE.md

Claude 在本仓库（今天你寸了吗 / chunithm-cun-sorter）工作时的约定与速查。

## 约定（必须遵守）

- **README 同步**：每次做了**功能 / 行为 / 配置项 / 命令 / 版本**上的改动，都要**同步更新 `README.md`** 的相应小节（功能特性、界面说明、判定与整理、`cun_config.json` 配置表、版本号、FAQ 等）。改代码与改文档算同一次改动 —— 不要只改代码、把 README 落下。
- 发版时一并更新 README 里的版本号与 zip 文件名（如 `v1.x` / `chunithm-cun-sorter_v1.x_win64.zip`）。

## 项目速查

- **技术栈**：WinUI 3 + .NET 8（Windows App SDK），非打包、自包含。工程在 `CunSorter/`，解决方案 `CunSorter.sln`。
- **编译**：`dotnet build CunSorter/CunSorter.csproj -c Release`
- **运行**：`dotnet run --project CunSorter -c Release`（GUI；用 `--no-build` 跑已编译版）
- **发版**：推送 `v*` tag → `.github/workflows/release.yml` 在 Windows runner 上构建自包含包并发 GitHub Release；根目录 `cun_config.json` 会作为**种子配置**打进包。
- **数据目录**：程序从 exe 起逐级向上找 `cun_config.json`；`bin/`、`obj/`、`cun_ocr_cache.json`、`cun.log` 已被 gitignore。
