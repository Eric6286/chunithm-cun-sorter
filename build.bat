@echo off
rem ============================================================
rem  Build 今天你寸了吗.exe (one-dir) with PyInstaller.
rem  Prereqs:  pip install -r requirements.txt pyinstaller
rem  Output:   app\今天你寸了吗.exe  (next to the source files)
rem ============================================================
chcp 65001 >nul
pushd "%~dp0"

python -m PyInstaller --noconfirm --clean --windowed ^
  --name "今天你寸了吗" --icon "icon.ico" ^
  --collect-all qfluentwidgets --hidden-import PySide6.QtCharts ^
  --exclude-module tkinter --exclude-module matplotlib ^
  --distpath "build_dist" --workpath "build_tmp" cun_gui.py
if errorlevel 1 goto :err

if exist "app" rmdir /s /q "app"
move "build_dist\今天你寸了吗" "app" >nul
rmdir /s /q "build_dist" "build_tmp" 2>nul
echo.
echo [OK] Built app\今天你寸了吗.exe
goto :done

:err
echo.
echo [FAIL] Build failed. Make sure: pip install -r requirements.txt pyinstaller

:done
popd
pause
