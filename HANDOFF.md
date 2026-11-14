# Stagecraft Studio 交接基线

本文件记录当前有效仓库拓扑、工程门禁、外部真实数据停点与后续待办。开发红线以 `AGENTS.md` 和 `D:\target-gene-scrna-stagecraft\docs\CURSOR_PRODUCT_BUILD_PLAN.zh-CN.md` 为准。

## 1. 四仓拓扑与状态

| 目录 | 角色 | 许可证 | 当前状态 |
| :--- | :--- | :--- | :--- |
| `D:\stagecraft-studio` | Studio 主应用（API、20/20 规则、Worker、SQLite 备份恢复、双语前端、受限 AI 适配层） | `GPL-3.0-only` | 速览闭环（M2/M3）、Part 1–5 流水线与分轮人工门禁（M4/M5 代码）、20/20 规则覆盖、受限助手离线闭环（M6 代码）、R 包探测与 SQLite 备份恢复 CLI 均已入库并通过本地门禁 |
| `D:\stagecraft-formal-engine` | 正式分析引擎（Part 1–5 donor 水平推断） | `GPL-3.0-only` | 源码已推送 `origin/master`，本地门禁与 GitHub Actions 双平台 + `r-models` CI 均已全绿通过 |
| `D:\scrna-target-engine` | 速览引擎（`quicklook` 细胞水平探索性分析，本地 GMT 富集） | `GPL-3.0-only` | 本地门禁与 GitHub Actions 双平台 CI 均通过 |
| `D:\target-gene-scrna-stagecraft` | 原始科学规格与产品任务书 | `MIT` | 规格基准 `2.4.0`（任务书仅保留在本地，不提交进该仓库） |

## 2. 已落地的产品与科学边界

- **无 AI 完整可跑**：Part 1–5 与速览均不依赖大模型；AI 助手仅读授权摘要并生成 `Proposal (DRAFT)`（如回填研究设计表单或展示只读候选名），无权改配置、冻结协议、提交审阅或抬高科学状态。
- **双档严格隔离**：速览产物带 `analysis_tier: quicklook`，正式入口拒绝读取；从速览带入正式分析仅保留数据路径、字段映射和目标基因；同项目先看速览目标基因结果再做正式审阅时，强制记录 `UNBLINDED_WITH_REASON`。
- **Part 1 分轮审阅顺序**：研究方案冻结 → 逐 library `load` / `qc` → 严格共同基因 `merge` → 9 档 Leiden `grid` → 人工选定 `resolution` → 自动生成逐群 QC 五数摘要（P5/P25/P50/P75/P95，无机器自动 QC 标签）与逐基因 Marker 证据表 → 人工提交 `KEEP/DELETE`（含 `DELETE` 则从保留 raw counts 重算下一轮 HVG/PCA/Harmony/Leiden；全 `KEEP` 则进入单独命名）→ 锁定 Part 1 图谱。
- **科学结论边界**：注释完成前服务端对 Part 2/4/5 与报告过滤目标基因；设计不足时保留 `NOT_ESTIMABLE`；校准状态固定保留 `NOT_ESTABLISHED_FOR_THIS_ANALYSIS`；留一来源块（LODO）不标记为独立外部复制。

## 3. 外部真实数据分析停点（仅继续真实分析时接触）

所有真实数据、SQLite 与分析输出均位于仓库外，禁止复制或提交进仓库：

- **数据目录**：`D:\geo_data\formal_atlas`（公开 GEO 3 个系列 `GSE233275` / `GSE272294` / `GSE280401`，共 16 个 10x library，目标基因 `STAT1`）。
- **有效数据库**：`D:\geo_data\formal_atlas\studio-gui-20261011.sqlite`（注意：同目录下 `studio-gui-20261011-before-reset-20261012.sqlite` 是缺少 WAL 的不完整副本，不可用于回滚或恢复）。
- **当前运行进度**：StageRun `#1`（协议 hash `157e94e4b433171a44176ed051edbd22db0af8372e3cfc2ed352b5967944deec`）已完成 16/16 `load`、16/16 `qc`、`merge`、9 档 `grid`；用户已提交 `resolution=0.5`，`formal_part1_review_tables` 已完成（7 个 Leiden 群、140 行 marker、QC 五数摘要齐全），当前停在 `REVIEW_CLUSTERS`。
- **严守红线**：尚未提交任何 `KEEP/DELETE` 或细胞群命名。必须由用户本人提交真实审阅判断，严禁用 `ARTIFICIAL_REVIEW_FIXTURE` 或示例名称代交。启动真实服务时须确保单进程 Worker 拥有写入 `D:\geo_data\formal_atlas` 的权限，避免双 Worker 争用 HDF5/SQLite 文件锁。

## 4. 本机验证命令

本机 `uv 0.9.2` 位于 `C:\Users\13305\AppData\Roaming\Python\Python310\Scripts\uv.exe`。在 `D:\stagecraft-studio` 执行全量验证：

```powershell
$uv = "C:\Users\13305\AppData\Roaming\Python\Python310\Scripts\uv.exe"
$env:Path = "D:\miniforge\envs\sc_analysis\Library\bin;" + $env:Path
$env:STAGECRAFT_FORMAL_SCRIPTS = "D:\stagecraft-formal-engine\scripts"
$env:STAGECRAFT_FORMAL_PYTHON = "D:\stagecraft-formal-engine\.venv\Scripts\python.exe"

& $uv run ruff check .
& $uv run ruff format --check .
& $uv run mypy
& $uv run python scripts/check_hygiene.py
& $uv run python scripts/export_rule_coverage.py --check
& $uv run python scripts/export_openapi.py --check
& $uv run pytest

pnpm -C web generate:api
git diff --exit-code -- web/src/api/schema.ts
pnpm -C web lint
pnpm -C web exec prettier --check .
pnpm -C web typecheck
pnpm -C web test
pnpm -C web e2e
```

## 5. 已完成的工程收尾与剩余人工/发布项

- **已完成（纯工程收尾）**：
  - `docs/rule-coverage.md` 全部 **20/20** 条规则均已落实并附可执行测试（含 `DONOR_MAPPING_REQUIRED` 供体映射入队阻断与审计落库、`QUICKLOOK_CLAIM_SCOPE` 速览摘要/方法/复现包主张范围校验，以及正式引擎对空白/NA `donor_id` 的拦截）。
  - 浏览器端到端覆盖扩充至 **5 条 Playwright E2E**：除速览演示与受限助手外，`web/e2e/formal.spec.ts` 完整覆盖研究方案冻结、Harmony 违规拦截、Part 1 分辨率选择、逐群 QC/Marker 表渲染、KEEP 与细胞群命名锁定、阶段工作区规则检查及图库 `NOT_ESTIMABLE` / 校准边界。
  - 环境自检新增正式分析 Part 5 所需 R 包（`jsonlite`、`Matrix`、`limma`、`edgeR`、`DESeq2`）完备性探测；CLI 新增 `stagecraft-studio backup` / `restore` 在线 WAL 一致性备份与完整性恢复校验。
  - 完成三仓运行时第三方依赖 `GPL-3.0-only` 许可证核验（写入 `docs/install.md` 与正式引擎 `THIRD_PARTY_NOTICES.md`）、10,000 细胞 / 4 文库正式引擎实测耗时基准（写入 `docs/architecture.md`），并加固正式引擎 GitHub Actions R 二进制依赖安装流程；正式引擎全量 `111 passed`，速览引擎全量 `28 passed`。
- **剩余待办（需真人审阅 / 外部凭据 / 远端发布与干净机器验证）**：
  1. **M5 真实数据人工审阅闭环**：启动 Studio 连接 `D:\geo_data\formal_atlas\studio-gui-20261011.sqlite`，由用户在界面审阅 QC / Marker 表并亲自提交 `KEEP/DELETE` 与稳定轮细胞群命名，随后继续跑 `Part 1 lock` → `Part 3` → `Part 2 / 4 / 5` 与阶段报告。
  2. **M6 真实外部模型端点联调**：待维护者提供真实外部模型端点与 API key 后做一次联调验收。
  3. **M7 干净机器验收**：已完成 `stagecraft-studio`（6/6 jobs）与 `stagecraft-formal-engine`（3/3 jobs，含 `r-models`）GitHub Actions 远端 CI 复验；剩余干净机器从零安装与 30 万细胞上限压测。
