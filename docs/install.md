# 安装与开发配置

## 工具版本要求

- **Python**：Studio 支持 `>=3.10,<3.12`（仓库 `.python-version` 为 `3.10`，CI 同时验证 `3.10` 与 `3.11`）；正式分析引擎与速览引擎要求 `>=3.11,<3.12`。不要使用 Python 3.12 及以上版本。
- **uv**：`0.9.2`（`pyproject.toml` 锁定 `required-version = "==0.9.2"`）。
- **Node.js**：`24`。
- **pnpm**：`12.8.1`。
- **R（正式分析 Part 5 需要）**：R `4.5.x` 及 `jsonlite`、`Matrix`、`limma`、`edgeR`、`DESeq2`。

## 一键启动（Windows）

将三个仓库置于同一父目录下（`stagecraft-studio`、`scrna-target-engine`、`stagecraft-formal-engine`），双击 `Start Studio.cmd`（调用 `scripts/start-studio.cmd`）。脚本会按锁文件同步环境、按需构建前端静态资源并在 `http://127.0.0.1:8765/` 启动本地服务。

## Python 环境与依赖说明

在仓库根目录同步锁文件：

```powershell
uv sync --frozen
```

运行时直接依赖（`pyproject.toml`）：

- `hatchling==1.32.4`：构建 `stagecraft_studio` 包。
- `fastapi==0.142.1`、`uvicorn==0.54.0`、`python-multipart==0.0.32`：仅绑定 `127.0.0.1` 的本地 API、表单解析与静态页面托管。
- `pydantic==2.13.5`：任务注册表参数、协议表单与受限助手 Proposal 的严格结构校验（拒绝未知字段）。
- `sqlalchemy==2.0.44`、`alembic==1.16.5`：本地 SQLite 元数据、审阅凭证、规则结果与版本迁移。
- `httpx==0.28.1`：可选 BYOK 助手调用用户显式配置的模型端点，同时供 FastAPI `TestClient` 使用。
- `keyring==25.6.0`：将可选模型 API key 存入操作系统凭据库，不落盘到 SQLite 或项目目录。
- 默认基因集使用标准库 `urllib` 下载 MSigDB Hallmark / GOBP 的 GMT 并校验固定 SHA-256，分析时不引入 `gseapy`，也不向外部发送基因列表。

开发依赖组（`dev`）：

- `ruff==0.16.9`：代码检查与格式化。
- `mypy==2.3.1`：静态类型检查（`domain` 与 `rules` 启用 `strict = true`）。
- `pytest==9.1.1`：单元与集成测试运行器。
- `pre-commit==4.6.2`：提交前执行 Ruff、Prettier 与 `scripts/check_hygiene.py`。

## 前端环境与依赖说明

```powershell
npm install -g pnpm@12.8.1
pnpm install --frozen-lockfile
```

前端依赖（`web/package.json`）：

- `react==19.3.0`、`react-dom==19.3.0`、`@types/react==19.3.0`、`@types/react-dom==19.3.0`：界面渲染。
- `vite==8.3.1`、`@vitejs/plugin-react==6.1.1`：前端构建。
- `react-resizable-panels==4.14.1`：三栏可调宽度布局并持久化到 `localStorage`。
- `shiki==4.4.3`：只读高亮引擎步骤脚本源码。
- `@tanstack/react-table==9.2.4`、`@tanstack/react-virtual==3.14.13`：分页 CSV 预览与虚拟滚动。
- `openapi-typescript==7.13.0`：从 `web/openapi.json` 自动生成 `web/src/api/schema.ts`，禁止手写接口类型。
- `typescript==5.9.3`、`eslint==10.11.0`、`@eslint/js==10.0.1`、`typescript-eslint==8.71.0`、`prettier==3.9.9`：严格类型（禁 `any`）、代码规范与格式化。
- `vitest==5.0.2`、`happy-dom==20.14.5`、`@playwright/test==1.63.0`：组件单测与浏览器端到端验收。

## 提交钩子

完成 `uv` 与 `pnpm` 依赖同步后安装 pre-commit：

```powershell
uv run pre-commit install
```

## Windows 运行环境补充（正式引擎与跨仓回归）

Windows 下运行正式引擎或跨仓科学回归测试时，底层数值库（NumPy/SciPy/Scanpy）依赖 OpenMP 运行时（`libiomp5md.dll`）。若报 `DLL load failed while importing _arpack`，需将单细胞环境动态库目录前置加入 `PATH`：

```powershell
$env:Path = "D:\miniforge\envs\sc_analysis\Library\bin;$env:Path"
```

运行真实正式引擎端到端串联测试（`tests/test_formal_real_chain.py`、`tests/test_formal_real_pipeline.py`）需显式指定正式引擎路径（CI 未配置这些变量时自动跳过）：

```powershell
$env:STAGECRAFT_FORMAL_SCRIPTS = "D:\stagecraft-formal-engine\scripts"
$env:STAGECRAFT_FORMAL_PYTHON = "D:\stagecraft-formal-engine\.venv\Scripts\python.exe"
```

## SQLite 状态备份与恢复

Studio 提供基于标准库 `sqlite3` 在线备份接口的命令行工具，可在 WAL 模式下生成一致性快照并附带 SHA-256、Alembic 版本与表行数清单（不打包 `.h5ad` 原始矩阵或系统凭据库密钥）：

```powershell
uv run stagecraft-studio backup --database path\to\studio.sqlite --out path\to\studio-backup.zip
uv run stagecraft-studio restore --backup path\to\studio-backup.zip --database path\to\restored.sqlite
```

恢复命令会在替换目标文件前校验压缩包成员白名单、SHA-256 摘要、`PRAGMA integrity_check` 与核心表行数；目标数据库已存在时默认拒绝覆盖（需显式加 `--overwrite`）。
