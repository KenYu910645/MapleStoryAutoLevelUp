@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================
echo   冒险岛挂机工具 - EXE 打包脚本
echo ============================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装项目依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

REM 安装 PyInstaller
echo.
echo [2/3] 安装 PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)

REM 清理旧的构建文件
echo.
echo [3/3] 开始打包...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 使用 spec 文件打包
pyinstaller maplestory_bot.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请检查上方错误信息
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包成功！
echo   输出文件: dist\MapleStoryBot.exe
echo ============================================
echo.
pause
