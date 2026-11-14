# 架构

许可证：`GPL-3.0-only`。形态：本地单用户模块化单体（FastAPI + SQLite + 单进程 Worker + React/TypeScript 前端）。

## 仓库与调用边界

- **Studio 主仓库（`D:\stagecraft-studio`）**：承载 HTTP API、会话与 Origin 校验、`@rule` 可执行规则层、线性失效状态机、SQLite 持久化、后台单任务 Worker、双语 Web 界面（`web/`）以及可选受限 AI 适配层（`stagecraft_studio/llm/`）。
- **正式分析引擎（`D:\stagecraft-formal-engine`）**：承载 Part 1–5 供体（donor）水平推断脚本与 `stagecraft_formal` 包；原始科学规格保留在 `D:\target-gene-scrna-stagecraft`。
- **速览引擎（`D:\scrna-target-engine`）**：承载单数据集细胞水平探索性分析（`analysis_tier: quicklook`），富集仅使用本地 GMT 文件离线运行。
- **跨仓边界**：Studio 仅以固定任务注册表和 Pydantic 校验后的参数通过子进程调用两个引擎脚本（禁止 `shell=True`、`eval`、`exec`、`pickle.load` 或跨仓 import `scripts/`）。两个引擎互不导入，前端仅用原生 `<img>` 展示引擎渲染的 PNG。

## 任务注册表与盲审边界

`stagecraft_studio/engine/registry.py` 固定登记 16 个任务 ID，未登记 ID 一律拒绝：

- **速览（2 项）**：`quicklook_run`、`quicklook_inspect`
- **Part 1 图谱与分轮审阅（7 项）**：`formal_part1_load`、`formal_part1_qc`、`formal_part1_merge`、`formal_part1_grid`、`formal_part1_round`、`formal_part1_review_tables`、`formal_part1_lock`
- **Part 2–5 与报告（7 项）**：`formal_part2_survey`、`formal_part2_figures`、`formal_part3_recluster`、`formal_part4_survey`、`formal_part4_figures`、`formal_part5_prepare`、`formal_stage_report`

其中 `formal_part2_*`、`formal_part4_*`、`formal_part5_prepare` 与 `formal_stage_report` 标记为 `TARGET_EXPOSING_TASKS`：在匹配的聚类人工审阅完成前或处于盲审期时，服务端在审阅证据、图库与原图下载接口统一过滤目标基因结果。

## 数据库与状态持久化

SQLite 结构统一由 Alembic 迁移管理（`0001_core_entities` 至 `0004_assistant`）：

- **核心分析与审计表**：`Project`、`ProtocolVersion`、`StageRun`、`Job`、`ReviewDecision`、`Artifact`、`RuleResult`、`AuditEvent`。
- **可选助手表（M6）**：`ProviderProfile`、`LLMCall`、`Proposal`（不存 API key 与原始模型响应；密钥仅存系统 `keyring` 或进程内存）。
- **速览状态说明**：速览运行当前仍以输出目录文件（`run_status.json`）维护状态，尚未并入 `StageRun` 表；速览目录带 `quicklook` 标记，正式分析入口强制拒绝读取。

四种状态独立存储，不合并为单一“通过”标记：`job_status`、`stage_status`、`scientific_status`（保留 `NOT_ESTIMABLE` 与校准未确立限制）、`artifact_status`（采用 `.studio/tmp/<job_id>/` 校验后原子发布，重跑旧产物记为 `SUPERSEDED`，上游变更触发下游线性 `INVALIDATED`）。

## 首版数据规模

状态：按以下规模施工，尚未做 30 万细胞峰值内存压测，暂未启用硬性 `RESOURCE_LIMIT` 阻断，也严禁静默抽样。

- 细胞数不超过 300,000
- library 数不超过 40
- 建议内存 32 GB

参考基线：策展集 `GSE167363`（64,244 细胞，QC 后 39,864 细胞）速览四阶段约 12 分钟；更大公开数据集结果目录可达数十 GB，Part 1 当前不使用 backed 模式。
