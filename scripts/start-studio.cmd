@echo off
setlocal
cd /d "%~dp0.."
set "PATH=%APPDATA%\Python\Python310\Scripts;%PATH%"
where uv >nul 2>&1
if errorlevel 1 (
  echo 没有找到 uv。请安装 uv 0.9.2，并把它加到 PATH。
  pause
  exit /b 1
)
where pnpm >nul 2>&1
if errorlevel 1 (
  echo 没有找到 pnpm。请安装 pnpm 12.8.1，并把它加到 PATH。
  pause
  exit /b 1
)
echo 同步 Studio...
uv sync --frozen
if errorlevel 1 goto fail
set "ENGINE=%CD%\..\scrna-target-engine"
if not exist "%ENGINE%\scripts\run_pipeline.py" (
  echo 没有找到引擎：%ENGINE%
  echo 请把 scrna-target-engine 放在 Studio 的上一级目录。
  pause
  exit /b 1
)
echo 同步引擎...
pushd "%ENGINE%"
uv sync --frozen
if errorlevel 1 goto fail
popd
if not exist "web\dist\index.html" (
  echo 构建页面...
  pnpm install --frozen-lockfile
  if errorlevel 1 goto fail
  pnpm -C web build
  if errorlevel 1 goto fail
)
set "PY=%ENGINE%\.venv\Scripts\python.exe"
set "SCRIPT=%ENGINE%\scripts\run_pipeline.py"
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8765/"
uv run python -m stagecraft_studio.engine.cli serve --port 8765 --python "%PY%" --script "%SCRIPT%"
exit /b %errorlevel%
:fail
echo 启动没有完成。
pause
exit /b 1
