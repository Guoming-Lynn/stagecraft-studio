# Stagecraft Studio

本地单用户分析壳。速览与正式分析由固定程序执行；可选 AI 助手支持本地解释和 BYOK 模型接入。模型未配置时，分析流程仍可独立运行。

## Windows 快速开始（测试版）

准备 uv 0.9.2、Node 24、pnpm 12.8.1，以及能用于 Python 3.11 的环境。正式分析还需要 R 和正式引擎所需的 R 包。第一次运行需要联网安装依赖；具体安装步骤见 `docs/install.md`。

将三个目录放在同一个上级目录：

```text
某个文件夹/
  stagecraft-studio/
  scrna-target-engine/
  stagecraft-formal-engine/
```

获取源码：分别下载或克隆 [Studio](https://github.com/Guoming-Lynn/stagecraft-studio)、[速览引擎](https://github.com/Guoming-Lynn/scrna-target-engine) 和 [正式引擎](https://github.com/Guoming-Lynn/stagecraft-formal-engine)，将解压后的目录命名为上图名称。

安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.9.2 和 [Node.js](https://nodejs.org/) 24，然后在终端运行 npm install -g pnpm@12.8.1。正式模型需要 R 的 jsonlite、Matrix，以及所选模型对应的 limma、edgeR 或 DESeq2。

双击 `stagecraft-studio/Start Studio.cmd`，等待依赖安装和浏览器打开。保持启动窗口打开；关闭窗口会停止服务。以后可以再次双击启动。首次启动耗时取决于网络和电脑，缺少工具或引擎时窗口会显示提示。

正式引擎缺失时只能使用速览。此版本仍在测试，真实数据尚未在界面中完成 Part 1–5 全流程验收。请先使用可公开的测试数据，分析结果需要由研究者审阅。

## 命令行启动

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

## 许可

本项目以 GPL-3.0-only 发布，详见 LICENSE。
