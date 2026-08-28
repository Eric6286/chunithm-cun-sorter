#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令出安装包。

    .venv\\Scripts\\python packaging\\build.py
    .venv\\Scripts\\python packaging\\build.py --skip-tests
    .venv\\Scripts\\python packaging\\build.py --no-installer

版本号的唯一真源是 ``core/version.py``：exe 的版本资源、安装包文件名、
控制面板里卸载项显示的版本全从那里读。

四步：跑测试 → PyInstaller 打 exe → **启动冒烟** → Inno Setup 出安装包。

冒烟那步不能省：**打包成功不等于跑得起来**。PyInstaller 漏掉一个隐藏依赖，
表现就是双击没反应、什么都不说——而这种问题只有真启动一次才看得见。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
DIST = ROOT / "dist" / "cun"

sys.path.insert(0, str(ROOT))
from core.version import APP_NAME, APP_USER_MODEL_ID, __version__   # noqa: E402

EXE = DIST / f"{APP_NAME}.exe"

#: 冒烟测试认这个窗口标题
WINDOW_TITLE_MARK = APP_NAME
#: 等窗口出现最多等这么久
SMOKE_TIMEOUT_SEC = 60


def step(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("  $ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


# ----------------------------- 版本资源 -------------------------------------
def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(x) for x in re.findall(r"\d+", version)][:4]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)                              # type: ignore[return-value]


def write_version_file(version: str) -> Path:
    """写 PyInstaller 的版本资源文件，让 exe 的「属性 → 详细信息」有内容。"""
    v = version_tuple(version)
    path = PKG / "file_version.txt"
    path.write_text(f"""# 由 packaging/build.py 生成，别手改。真源是 core/version.py。
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v}, prodvers={v},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('080404b0', [
      StringStruct('CompanyName', 'ErikaAlk'),
      StringStruct('FileDescription', '{APP_NAME}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'chunithm-cun-sorter'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{version}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
""", encoding="utf-8")
    return path


# ----------------------------- 各步骤 ---------------------------------------
def run_tests() -> None:
    step("跑测试")
    run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], cwd=ROOT)


def build_exe() -> None:
    step("PyInstaller 打 exe")
    for d in (ROOT / "build", ROOT / "dist"):
        shutil.rmtree(d, ignore_errors=True)
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         str(PKG / "cun.spec")], cwd=ROOT)
    if not EXE.is_file():
        raise SystemExit(f"打包没产出 exe：{EXE}")
    print(f"  产物：{EXE}（{_dir_size_mb(DIST):.0f} MB）")


def smoke_test() -> None:
    """真启动一次，等主窗口出现，然后关掉。"""
    step("启动冒烟")
    import ctypes
    from ctypes import wintypes

    with tempfile.TemporaryDirectory(prefix="cun-smoke-") as tmp:
        # 预置一份配置，免得弹首次运行向导把主窗口挡住
        shots = Path(tmp) / "screenshots"
        shots.mkdir()
        (Path(tmp) / "cun_config.json").write_text(
            json.dumps({"screenshots_dir": str(shots), "output_root": str(shots)},
                       ensure_ascii=False),
            encoding="utf-8")
        # 开发机上多半正跑着一份正式版，单实例那道闸会让冒烟进程静默退出，
        # 看起来就像「打包失败」。这里显式绕过。
        env = dict(os.environ, CUN_DATA_DIR=tmp, CUN_ALLOW_MULTIPLE="1")
        proc = subprocess.Popen([str(EXE)], env=env)
        try:
            deadline = time.monotonic() + SMOKE_TIMEOUT_SEC
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise SystemExit(f"exe 启动后自己退了，返回码 {proc.returncode}")
                if _find_window(proc.pid, ctypes, wintypes):
                    print(f"  主窗口出现了（{time.monotonic() - (deadline - SMOKE_TIMEOUT_SEC):.1f}s）")
                    return
                time.sleep(0.5)
            raise SystemExit(f"{SMOKE_TIMEOUT_SEC}s 内没等到主窗口，八成是缺依赖")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def _find_window(pid: int, ctypes_mod, wintypes_mod) -> bool:
    user32 = ctypes_mod.WinDLL("user32", use_last_error=True)
    proc_type = ctypes_mod.WINFUNCTYPE(
        wintypes_mod.BOOL, wintypes_mod.HWND, wintypes_mod.LPARAM)
    hit: list[bool] = []

    def cb(hwnd, _lparam):
        owner = wintypes_mod.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes_mod.byref(owner))
        if owner.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes_mod.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if WINDOW_TITLE_MARK in buf.value:
            hit.append(True)
            return False
        return True

    user32.EnumWindows(proc_type(cb), 0)
    return bool(hit)


def find_iscc() -> Path:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6/ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6/ISCC.exe",
    ]
    for c in candidates:
        if c.is_file():
            return c
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    raise SystemExit("找不到 ISCC.exe。装一下：winget install --id JRSoftware.InnoSetup")


def build_installer(version: str) -> None:
    step("Inno Setup 出安装包")
    iscc = find_iscc()
    run([str(iscc), f"/DAppVersion={version}",
         f"/DAppUserModelID={APP_USER_MODEL_ID}", str(PKG / "installer.iss")], cwd=PKG)
    out = ROOT / "dist_installer"
    made = sorted(out.glob(f"*{version}*.exe"), key=lambda p: p.stat().st_mtime)
    if not made:
        raise SystemExit(f"没在 {out} 里找到安装包")
    print(f"  产物：{made[-1]}（{made[-1].stat().st_size / 1e6:.0f} MB）")


def _dir_size_mb(d: Path) -> float:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e6


def main() -> int:
    parser = argparse.ArgumentParser(description=f"打包 {APP_NAME}")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试")
    parser.add_argument("--skip-smoke", action="store_true", help="跳过启动冒烟（不建议）")
    parser.add_argument("--no-installer", action="store_true", help="只打 exe，不出安装包")
    args = parser.parse_args()

    print(f"{APP_NAME} {__version__}")
    if not args.skip_tests:
        run_tests()
    write_version_file(__version__)
    build_exe()
    if not args.skip_smoke:
        smoke_test()
    if not args.no_installer:
        build_installer(__version__)
    print("\n全部完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
