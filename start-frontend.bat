@echo off
echo ========================================
echo 专利-标准比对系统 V1.0 - 前端启动脚本
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%\frontend"

echo [1/2] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [2/2] 启动 HTTP 服务器...
echo.
echo 前端服务启动中...
echo 访问地址: http://localhost:3000
echo.
echo 按 Ctrl+C 停止服务
echo.

python -m http.server 3000 --bind 127.0.0.1
