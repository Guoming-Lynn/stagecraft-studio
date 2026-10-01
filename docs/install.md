# 安装

M0 只安装开发工具。不安装 scanpy、FastAPI 或模型 SDK。

## 工具

- Python 3.10 或 3.11。本机已验证的是 3.10.8。
- uv 0.9.2。`pyproject.toml` 把版本锁在这一版。
- Node 24。
- pnpm 12.8.1。

不要用 Python 3.12 及以上。

## Python

在仓库根目录：

```text
uv sync --frozen
```

直接依赖及理由：

- hatchling 1.32.4：构建这一个 Python 包。标准库没有打包后端。
- pydantic 2.13.5：校验 `quicklook_run` 和 `quicklook_inspect` 的参数。标准库没有带类型和多余字段拒绝的模型。
- fastapi 0.142.1 与 uvicorn 0.54.0：本地表单和只监听 127.0.0.1 的进程。标准库没有请求校验。
- python-multipart 0.0.32：FastAPI 解析表单时需要它。
- httpx 0.28.1（开发依赖）：FastAPI 的测试客户端需要它。
- 默认基因集用标准库 `urllib` 下载 MSigDB 的 GMT。不把 gseapy 加进 Studio，分析时也不把基因列表发出去。
- ruff 0.16.9：任务书指定的检查和格式化工具。
- mypy 2.3.1：任务书指定的类型检查。`domain` 与 `rules` 使用 strict。
- pytest 9.1.1：任务书指定的测试运行器。
- pre-commit 4.6.2：提交前运行 ruff、prettier 和卫生检查。

## 前端

```text
npm install -g pnpm@12.8.1
pnpm install --frozen-lockfile
```

直接依赖及理由：

- typescript 5.9.3：`tsc --noEmit`。5.9 落在 typescript-eslint 8.71 支持的范围内。
- eslint 10.11.0、@eslint/js 10.0.1、typescript-eslint 8.71.0：检查 TypeScript，并禁止 `any`。
- prettier 3.9.9：任务书指定的前端格式化工具。
- vitest 5.0.2：任务书指定的前端测试运行器。
- react 19.3.0、react-dom 19.3.0、@types/react 19.3.0、@types/react-dom 19.3.0：界面规格要求 React。M0 骨架没有现成的 React 版本。
- vite 8.3.1、@vitejs/plugin-react 6.1.1：打包页面。vitest 5 接受 vite 8。
- react-resizable-panels 4.14.1：三栏拖动，并把宽度存进 localStorage。
- shiki 4.4.3：只读高亮步骤源码。不需要编辑器。
- @tanstack/react-table 9.2.4、@tanstack/react-virtual 3.14.13：规格要求预先钉住，给 E2 的 CSV 查看器。E1 还没有 import。
- openapi-typescript 7.13.0：从 OpenAPI 生成 `web/src/api/schema.ts`。前端不手写接口类型。
- happy-dom 20.14.5：vitest 渲染组件时需要 DOM。
- @playwright/test 1.63.0：浏览器验收。标准库和 vitest 打不开真实页面，也不能点按钮、下载 zip。

## 提交钩子

安装 uv 和 pnpm 并完成上面的同步之后：

```text
uv run pre-commit install
```
