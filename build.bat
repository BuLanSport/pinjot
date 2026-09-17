@echo off
rem 一键打包成单文件 exe，产物在 dist\PinJot.exe
setlocal
cd /d "%~dp0"

echo [1/3] 检查 PyInstaller...
py -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo     未安装，正在安装 PyInstaller 和 Pillow...
    py -m pip install pyinstaller pillow || goto :fail
)

echo [2/3] 生成图标...
py tools\make_icon.py || goto :fail

echo [3/3] 开始打包...
py -m PyInstaller --noconfirm --clean --onefile --noconsole ^
    --name PinJot --icon assets\pinjot.ico ^
    --add-data "assets\pinjot.ico;assets" ^
    pin_note.py || goto :fail

echo.
echo 打包完成：dist\PinJot.exe
exit /b 0

:fail
echo.
echo 打包失败，请查看上面的错误信息
exit /b 1
