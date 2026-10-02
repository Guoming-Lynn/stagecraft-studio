# Stagecraft Studio

本地单用户分析壳。当前可以提交速览，不连接模型。

## 安装

需要 Python 3.10 或 3.11、uv 0.9.2、Node 24、pnpm 12.8.1。步骤见 `docs/install.md`。

## 启动

本地页面只监听 127.0.0.1，并在聚类之后停住，不调用在线富集。引擎解释器和 `run_pipeline.py` 只在启动时确定，表单不能改它们。设置环境变量，或给 `serve` 传启动参数：

```text
set STAGECRAFT_QUICKLOOK_PYTHON=PATH\to\python.exe
set STAGECRAFT_QUICKLOOK_SCRIPT=PATH\to\run_pipeline.py
uv run python -m stagecraft_studio.engine.cli serve --port 8765
```

也可以不打开页面，直接跑。`quicklook` 读取同一对环境变量：

```text
uv run python -m stagecraft_studio.engine.cli quicklook --input DATA.h5ad --gene GENE --out PROJECT
```

`PYTHON` 是装有速览依赖的解释器。输出目录必须是新的或空的。

## 测试

```text
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run python scripts/check_hygiene.py
uv run python scripts/export_rule_coverage.py --check
uv run python scripts/export_openapi.py --check
pnpm install --frozen-lockfile
pnpm -C web lint
pnpm -C web exec prettier --check .
pnpm -C web typecheck
pnpm -C web test
pnpm -C web e2e
```

### 真实正式引擎端到端串联测试

正式分析引擎与 Studio 跨进程交互测试（`test_formal_real_chain.py` 与 `test_formal_real_pipeline.py`）需要通过环境变量指定正式引擎解释器及脚本目录：

```text
set STAGECRAFT_FORMAL_SCRIPTS=D:\stagecraft-formal-engine\scripts
set STAGECRAFT_FORMAL_PYTHON=D:\stagecraft-formal-engine\.venv\Scripts\python.exe
uv run pytest tests/test_formal_real_chain.py tests/test_formal_real_pipeline.py
```

在未建立私有远端 CI 跨仓库集成前，本地提交前必须设置上述环境变量并跑通全量 `uv run pytest`（包括上述真实端到端串联用例）。未设置环境变量时，该两项测试会自动跳过（skipped）。
