# 架构

状态：M0-A 骨架。没有标成「已确认」的内容都还不是决定。

## 已由任务书定下的边界

- Studio 以子进程调用两个引擎，不 import 对方仓库的 `scripts`。
- 正式分析引擎在 `D:\stagecraft-formal-engine`。skill 仓库只保留规格。
- 速览引擎在 `D:\scrna-target-engine`。
- 本地单用户：一个 worker、SQLite、线性阶段失效。SQLite 从 M4 G4 开始。
- 本仓库有速览任务，以及 `formal_part1_load`、`formal_part1_qc`、`formal_part1_merge`、`formal_part1_grid`。

## SQLite

M4 G4 起用 SQLite 和 Alembic。第一版修订建立 Project、ProtocolVersion、StageRun、Job、ReviewDecision、Artifact、RuleResult、AuditEvent。速览的 `run_status.json` 和 `state_path` 还没有迁进来。

## 首版数据规模

状态：按此施工。维护者要求先做雏形，不把这一步再停成待确认。数字仍可改，也还不是压测结论。

建议仍采用任务书起点：

- 细胞数不超过 300000
- library 数不超过 40
- 内存 32 GB

依据：2026-09-30 重跑了策展集里最小的可重跑输入 `GSE167363`，64244 个细胞，QC 后 39864，四阶段约 12 分钟。更大的策展输入到数 GB，`GSE290679` 的结果目录约 24 GB。峰值内存没有测量，300000 细胞没有压测。Part 1 没有 backed 模式。确认之前不实现 `RESOURCE_LIMIT`，也不静默抽样。
