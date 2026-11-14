# Stagecraft Studio 交接基线

本文件记录当前有效仓库拓扑、工程门禁、外部真实数据停点与后续待办。开发红线以 `AGENTS.md` 和 `D:\target-gene-scrna-stagecraft\docs\CURSOR_PRODUCT_BUILD_PLAN.zh-CN.md` 为准。

## 1. 四仓拓扑与状态

| 目录 | 角色 | 许可证 | 当前状态 |
| :--- | :--- | :--- | :--- |
| `D:\stagecraft-studio` | Studio 主应用（API、规则、Worker、SQLite、双语前端、受限 AI 适配层） | `GPL-3.0-only` | 速览闭环（M2/M3）、Part 1–5 流水线与分轮人工门禁（M4/M5 代码）、受限助手离线闭环（M6 代码）均已入库并通过本地门禁 |
| `D:\stagecraft-formal-engine` | 正式分析引擎（Part 1–5 donor 水平推断） | `GPL-3.0-only` | 脚本与 `stagecraft_formal` 包已完成并过本地门禁；远端仓库源码尚未推送 |
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

## 5. 剩余三条待办线

1. **线 A — M5 真实数据全流程闭环**：启动 Studio 连接 `D:\geo_data\formal_atlas\studio-gui-20261011.sqlite`，由用户在界面审阅 QC / Marker 表并提交 `KEEP/DELETE` 与稳定轮细胞群命名，随后按注册任务推进 `Part 1 lock` → `Part 3` → `Part 2 / 4 / 5` 与阶段报告。
2. **线 B — 规则函数补齐**：在 `stagecraft_studio/rules/` 中落实 `docs/rule-coverage.md` 尚余的两项（`DONOR_MAPPING_REQUIRED`、`QUICKLOOK_CLAIM_SCOPE`）并同步导出覆盖表与测试。
3. **线 C — M1 / M6 / M7 验收与发布收尾**：
   - `M1`：在速览引擎上完成至少两个 `06_curated_results` 数据集基线复跑与容差记录；
   - `M6`：维护者提供真实外部模型端点与 API key 后做一次联调验收；
   - `M7`：推送 `stagecraft-formal-engine` 远端并跑通 CI、核对第三方依赖许可证声明、干净机器安装验证、规模耗时压测与备份恢复演练。
