@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
where uv >nul 2>&1
if errorlevel 1 (
  echo 没有找到 uv 0.9.2。请先按照 README 中的安装说明安装。
  pause
  exit /b 1
)
where pnpm >nul 2>&1
if errorlevel 1 (
  echo 没有找到 pnpm 12.8.1。请先按照 README 中的安装说明安装 Node 和 pnpm。
  pause
  exit /b 1
)
set "ENGINE=%CD%\..\scrna-target-engine"
if not exist "%ENGINE%\scripts\run_pipeline.py" (
  echo 没有找到速览引擎：%ENGINE%
  echo 请将 scrna-target-engine 与 stagecraft-studio 放在同一个上级目录。
  pause
  exit /b 1
)
echo 正在准备 Studio，首次运行可能需要较长时间...
uv sync --frozen
if errorlevel 1 goto fail
set "FORMAL_ENGINE=%CD%\..\stagecraft-formal-engine"
if exist "%FORMAL_ENGINE%\scripts\part1_load.py" (
  echo 正在准备正式分析引擎...
  pushd "%FORMAL_ENGINE%"
  uv sync --frozen
  if errorlevel 1 goto fail
  popd
  if not defined STAGECRAFT_FORMAL_SCRIPTS set "STAGECRAFT_FORMAL_SCRIPTS=%FORMAL_ENGINE%\scripts"
  if not defined STAGECRAFT_FORMAL_PYTHON set "STAGECRAFT_FORMAL_PYTHON=%FORMAL_ENGINE%\.venv\Scripts\python.exe"
) else (
  echo 未在同级目录找到正式分析引擎。
  echo 如需正式分析，请把 stagecraft-formal-engine 放在同一个上级目录，或设置正式引擎环境变量。
)
echo 正在准备速览引擎...
pushd "%ENGINE%"
uv sync --frozen
if errorlevel 1 goto fail
popd
uv run python -m stagecraft_studio.web_freshness
if not errorlevel 1 goto page_ready
echo 正在构建页面...
call pnpm install --frozen-lockfile
if errorlevel 1 goto fail
call pnpm -C web build
if errorlevel 1 goto fail
:page_ready
set "PY=%ENGINE%\.venv\Scripts\python.exe"
set "SCRIPT=%ENGINE%\scripts\run_pipeline.py"
echo 正在启动 Studio，请保持此窗口打开。
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8765/"
uv run python -m stagecraft_studio.engine.cli serve --port 8765 --python "%PY%" --script "%SCRIPT%"
if errorlevel 1 goto fail
exit /b 0
:fail
echo 启动没有完成。请查看上方错误信息。
pause
exit /b 1
