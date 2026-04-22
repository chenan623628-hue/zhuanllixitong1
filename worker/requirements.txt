@echo off
echo ========================================
echo 专利-标准比对系统 V1.0 - 后端启动脚本
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%\backend"

echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [2/4] 创建虚拟环境...
if not exist "venv" (
    python -m venv venv
)

echo [3/4] 激活虚拟环境并安装依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q

echo [4/4] 启动服务...
echo.
echo 服务启动中...
echo 访问地址: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
