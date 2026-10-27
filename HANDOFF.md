# Stagecraft Studio 接手记录

> **当前有效状态，2026-10-12 真人试用中**
>
> 这一节是压缩上下文后的首要入口。下方较早的续接/打断记录用于追溯历史，若与本节冲突，以本节和 `docs/milestones.md` 最新 M5 状态为准。
>
> - 仓库：`D:\stagecraft-studio`；分支：`feat/bioinformatics-terminology-i18n`。工作区已有大量未提交改动，禁止 reset、clean、checkout、stash 或 push；修改前先检查 `git status`。
> - 当前进行的事：用户正在对 Studio 做真人完整试用，边操作边给出术语和交互反馈。新版页面地址为 `http://127.0.0.1:8796/`（8795 被旧进程占用）。不要为了试用自动完成任何科学审阅。
> - 真实数据与数据库均在仓库外。数据：`D:\geo_data\formal_atlas`；数据库：`D:\geo_data\formal_atlas\studio-gui-20261011.sqlite`。StageRun `#1`，协议 hash `157e94e4b433171a44176ed051edbd22db0af8372e3cfc2ed352b5967944deec`，状态 `READY`。
> - 真实分析进度：16/16 Part 1 load、16/16 QC、merge、9 档 resolution grid 均完成。真实 Run #1 刚从旧 resolution `0.5` 回退至 `CHOOSE_RESOLUTION`；原人工 resolution 记录、旧 review-table job/artifact 与旧表目录已清理。未提交 cluster KEEP/DELETE 或命名。曾复制主数据库文件到 `D:\geo_data\formal_atlas\studio-gui-20261011-before-reset-20261012.sqlite`，但该 SQLite 使用 WAL，副本未包含 0.5 记录，不是完整回滚备份，不得用于恢复。
> - Part 3 图库缺失原因已查明并修复代码：当前真实 StageRun 尚未进入 Part 3；图库此前也漏了 Part 3 分类/筛选。现在有 Part 3 筛选入口，并在该运行无 Part 3 产物时显示明确提示。后端测试 fixture 已确认分类与盲审规则。
> - 近期界面工作：术语中英双语；正式分析层级与窄屏可读性；科学状态改成结论、分列状态与简明证据边界；图库增加 Part 3。API 状态码、科学规则、真实数据库和审阅凭据没有因这些改动而修改。
> - 最近验证：图库 Python 测试 `5 passed`；Web Vitest `14 passed`；Web typecheck、ESLint、Prettier、生产构建通过。Playwright 本地浏览器确认 Part 3 筛选入口和“尚未生成”提示。`git diff --check` 通过。
> - 试用期间：只针对用户实际操作反馈做小步界面修正；若涉及科学状态或数据解释，保留服务器码与原始证据，不替用户解释为更强结论。真人审阅只能由用户提交。StageRun #1 上看到 quicklook 目标基因结果后，按规则需 `UNBLINDED_WITH_REASON` 并填写理由。
> - 用户试用后的续接顺序：整理用户反馈并修界面；用户亲自完成真实 Part 1 resolution/cluster 审阅；之后按注册任务推进 Part 1 lock、Part 3、Part 2/4/5。Part 5 是否拟合取决于 donor、condition、source-block 可估计性。之后再继续 M1/M7；M6 真实模型端点仍须维护者提供服务和凭据才可验收。
> - 测试环境：Studio `.venv\Scripts\python.exe`；正式引擎 Python `D:\stagecraft-formal-engine\.venv\Scripts\python.exe`；正式脚本 `D:\stagecraft-formal-engine\scripts`；R 位于 PATH。全量正式引擎集成测试需要 `STAGECRAFT_FORMAL_SCRIPTS`、`STAGECRAFT_FORMAL_PYTHON`，Windows 还需 `D:\miniforge\envs\sc_analysis\Library\bin` 加入 PATH。

更新时间：2026-10-12（Europe/Berlin）

## 2026-10-13 下班交接

- 今天完成 Marker 证据表的浏览体验修订：顶部新增与表格同步的横向滚动条，Marker 表放入固定高度纵向视口，纵向滚动时表头保持可见；不需要滚到 140 行表格底部才能左右查看。
- 真实 Run #1 当前状态：`resolution=0.5` 已由用户提交，`formal_part1_review_tables` 已完成；API 返回 7 个 Leiden 群、140 行 marker、QC 五数摘要字段完整，状态为 `REVIEW_CLUSTERS`。没有提交任何 KEEP/DELETE 或群体命名。
- 明天继续使用 `http://127.0.0.1:8796/`，在“表格”中查看 QC 与 Marker 证据，然后由用户本人提交群体去留。若有 DELETE，按原计划从保留的 raw counts 进入下一轮 HVG/PCA/Harmony/Leiden；若全部 KEEP，再进入人工命名和 Part 1 锁定。
- 本轮验证：TypeScript、ESLint、Vitest（14 项）、生产构建、Chromium 1600×1000 交互检查和 Impeccable detector 均通过。Formal Engine pytest 在本机 Windows 环境长时间无输出，未确认通过，不要据此宣称全量 Python 回归通过。

## 2026-10-13 Part 1 QC 表格修订

- 用户认为机器规则给 Leiden 群贴 QC 复核提示不合适，要求移除；同时要求 QC 指标展示 P5、P25、中位数、P75、P95。已从 Formal Engine 删除群级 `qc_flags` 规则和 stress-marker flag，API 不再计算或返回 QC flags；前端审阅页和表格页去掉自动 QC 复核段落。
- QC CSV 对 UMI、检出基因数、线粒体/血红蛋白/核糖体比例、Top 50 占比、基因/UMI 复杂度、Scrublet 评分计算五数摘要。前端按“cluster × QC 指标”列出，每行用带 P5/P25/P50/P75/P95 标签的紧凑摘要显示全部分布，不需横向滚动；群体筛选同时作用于 QC 和 marker 表。供体/数据集/文库数、最大数据集占比和谱系 marker 命中仍作为描述统计保留。
- 真实 Run #1 的 `resolution=0.5` 仍由用户选择，StageRun 保持 `REVIEW_CLUSTERS`；FormalWorker 新排任务 #46 已重新发布新版 QC/marker 表。API 返回 7 群、140 条 marker、40 个 quantile 字段且不含 `qc_flags`。
- 验证：前端 TypeScript、ESLint、Vitest（14 项）通过，生产构建已更新。Playwright 在 1600px 桌面窗口中检查右侧窄栏，确认无横向滚动、7 群共 56 项指标、分位数标签与数值完整、QC 自动提示消失。Formal Engine pytest 在当前 Windows 环境启动后长时间无输出，尚未确认完成；不可报告为通过。

## 2026-10-13 Marker 表滚动体验

- 用户反馈 Marker 表太长，原生横向滚动条在表格最底部，左右查看很麻烦。已在 Marker 证据视图增加顶部同步横向滚动条；它与表格视口共享 `scrollLeft`，最大滚动距离校准一致。表格视口固定为 `min(58vh, 560px)`，纵向滚动时表头保持在视口顶部，不再需要滚到表格末尾找横向条。
- QC 五数摘要表不横向溢出，不额外增加滚动轨道。顶部轨道带中英文可访问名称、焦点轮廓和原生滚动条，支持鼠标、键盘和触摸横向滚动。
- 浏览器验证（Chromium，1600×1000）：Marker 表 140 行；顶部轨道和表格 `scrollLeft` 同步，纵向滚动 500px 后表头 top 与视口 top 相同。Impeccable detector 返回空结果。
- 验证：TypeScript、ESLint、Vitest（14 项）、生产构建通过。真实 Run #1 仍为 `REVIEW_CLUSTERS`，未提交任何 cluster KEEP/DELETE 或命名。

## 2026-10-13 分辨率提交故障与主题默认值

- 真人试用时选择分辨率返回 `Internal Server Error`。服务日志确认是进程以受限权限打开仓库外 SQLite，写入人工审阅记录时触发 `sqlite3.OperationalError: attempt to write a readonly database`。请求未写入 resolution 决策，Run #1 仍保持 `READY / CHOOSE_RESOLUTION`。
- 8795 是旧服务；排障时曾误把 8796 的服务重启为受限进程，用户继续在旧页面试用，所以再次遇到相同错误。现已停止占用 8796 的旧进程，并以可写权限启动新版服务；稳定运行 10 秒后 API 返回 200。真实数据库目录写入探针成功并清理。继续试用必须使用 `http://127.0.0.1:8796/`，不要使用 8795。
- 启动时必须保留 `STAGECRAFT_DATABASE`、`STAGECRAFT_FORMAL_*`、`STAGECRAFT_QUICKLOOK_*` 与 `PYTHONPATH` 配置；进程必须具有写入 `D:\geo_data\formal_atlas` 的权限。
- 重新启动后的稳定服务已实际接受 `resolution=0.5`（HTTP 201），`formal_part1_review_tables` 已完成；Run #1 当前为 `REVIEW_CLUSTERS`，QC 汇总 7 行、Marker 证据 140 行。后续进入人工 KEEP/DELETE，勿重复提交 resolution。
- 用户反馈默认深色主题观感不好。前端启动默认主题已改为浅色；若浏览器已有 `stagecraft_theme` 偏好，则继续尊重该偏好。生产 bundle 已重建。


## 2026-10-12 新版表格试用准备

- 用户要求撤销刚才选定的 resolution 并清理旧表格，以试用修复版。核查确认 StageRun #1 只有 `0.5` 的 resolution 决定和 `formal_part1_review_tables` job #45，没有 cluster KEEP/DELETE 或命名。
- 曾复制 SQLite 主文件至 `D:\geo_data\formal_atlas\studio-gui-20261011-before-reset-20261012.sqlite`，但后续只读核验发现 WAL 中的 resolution 记录没有进入该副本；文件 `integrity_check=ok`，却不是完整回滚备份。再通过当前数据库事务删除该 resolution 审阅、job #45 及其 artifact 记录；清理 `analysis\stage_1\formal_part1_grid\review_tables`。重置 evidence 中的活动 resolution/cluster 与 review table 标记，`leiden_ids_json=[]`，StageRun 保持 `READY`。只保留 grid 原始分辨率概览。
- 8795 端口仍由旧进程占用，当前权限无法枚举其监听 PID。已在仓库外 `D:\geo_data\formal_atlas\studio-venv-314` 建立 Python 3.14 临时运行环境（项目 `.venv` 绑定的 Python 3.10 已不存在），新版 Studio 在 8796 启动；使用同一数据库和当前源码。`web/dist` 已重建，新服务首页 HTTP 200，静态资源指向新 bundle。
- 用户从 `http://127.0.0.1:8796/` 继续体验。重新选择 resolution 后会生成新版 QC 与 marker 表；不要自动提交 KEEP/DELETE 或命名。`*-before-reset-20261012.sqlite` 只是 WAL 不完整副本，不可用于回滚。

### 2026-10-11 真人试用：Part 1 表格审阅第一版

- 在右侧“图像 / 表格 / 助手”中新增“表格”。它读取正式运行目录中固定命名的 `leiden_r*_cluster_qc.csv` 和 `leiden_r*_top20_by_cluster.csv`，不在 Studio API 内重新计算细胞级 QC 或 marker。
- 逐群表展示细胞数、中位 UMI、中位检出基因数、中位线粒体比例、Top 20 marker 和 QC 复核提示。提示规则对应原计划：小群、线粒体比例明显偏高、来源集中且无谱系标记、应激基因占优且无谱系标记。
- 复核提示只供人工判断，不会自动修改 KEEP/DELETE、命名或科学状态。当前 StageRun #1 尚未选择 resolution，正式运行尚无 marker/QC 表，因此表格页显示“选定分辨率后才会生成”。
- 验证：项目 Python `tests/test_review_gates.py` 11 passed；Web typecheck、ESLint、Vitest 14 passed、生产构建通过。Python 测试使用仓库 `.venv`，系统 Python 缺少 FastAPI 不作为验证环境。

## 当前任务

历史目标按 `D:\target-gene-scrna-stagecraft\docs\CURSOR_PRODUCT_BUILD_PLAN.zh-CN.md` 推进。当前转入用户授权的真人交互试用；上方“当前有效状态”是下一轮入口。

## 仓库状态

- 工作目录：`D:\stagecraft-studio`
- 当前已有大量用户/前序工作区改动，未提交；不要 reset、clean、checkout 或覆盖无关改动。
- 本轮此前已完成的代码改动仍在工作区，涉及 Studio 正式引擎发现、图库科学状态、前端状态显示和相关测试。
- 接手与进度只维护 HANDOFF.md、docs/milestones.md 和 CHANGELOG.md；README 只记录安装、启动与测试。
- 真实数据、临时运行目录和分析输出均不在仓库内。

## 已验证的数据

数据缓存目录：`D:\geo_data\formal_atlas`

来源为真实 GEO 10x 原始 library：

- `GSE233275`：8 个 library（`GSM7421504_HC1` 至 `GSM7421511_INS4`）
- `GSE272294`：4 个 library（`GSM8397940_NT1`、`GSM8397941_LL1`、`GSM8397942_NT2`、`GSM8397943_LL2`）
- `GSE280401`：4 个 library（`GSM8596781_G` 至 `GSM8596784_D`）

原始包和拆出的 `matrix.mtx.gz`、`features.tsv.gz`、`barcodes.tsv.gz` 均已在 `D:\geo_data\formal_atlas\raw` 和 `D:\geo_data\formal_atlas\extracted` 留存。原始 tar SHA-256 记录在前序交接信息中：

- `GSE233275_RAW.tar`: `45669D3481449A020A69B2DD3184688E2B1825BC0AA6FCDCA3F558F246EB56BB`
- `GSE280401_RAW.tar`: `58495628B25F4349A2E3086F79CB66F50711CC9A1602E2B68BB29B4A760DA45C`

目标基因：`STAT1`。它存在于 16 个 library 的严格共同基因集中。

## 正式测试输出

所有输出目录：

`D:\CodexData\visualizations\2026\10\09\01a12000-d442-7f11-8995-fc98ce5f0d67\formal-real-rerun`

临时输入目录使用硬链接指向 `D:\geo_data\formal_atlas\extracted`，不会重复占用原始数据空间。

已完成：

1. 16/16 `part1_load.py` 成功。
2. 16/16 `part1_qc.py` 成功，Scrublet 状态均为 `ok`。
3. QC 后总保留细胞数：`119413`。
4. `part1_merge.py` 成功：`119413` cells × `20777` strict-common genes；3 datasets；16 donors；`STAT1` 存在。
5. `part1_resolution_grid.py` 成功：PCA/Harmony（Harmony key 为 `dataset`）、9 个 Leiden resolution、UMAP 和审计表均已生成。

关键文件：

- `analysis\stage_1\formal_part1_merge\primary_common.h5ad`
- `analysis\stage_1\formal_part1_grid\all_resolutions.h5ad`
- `analysis\stage_1\formal_part1_grid\Leiden_resolution_overview.csv`
- `analysis\stage_1\formal_part1_grid\grid_record.json`
- `clean_manifest.json`
- `artificial_review_fixture.json`

resolution grid 的真实概览：

| resolution | clusters |
|---:|---:|
| 0.2 | 7 |
| 0.3 | 8 |
| 0.4 | 8 |
| 0.5 | 10 |
| 0.6 | 11 |
| 0.8 | 14 |
| 1.0 | 17 |
| 1.2 | 19 |
| 1.5 | 22 |

## 重要限制

`artificial_review_fixture.json` 明确标记为 `ARTIFICIAL_REVIEW_FIXTURE`，只用于验证工程串联。它不是用户真实审阅，不能作为科学结果、默认分辨率、细胞类型命名或正式审阅凭据。

本轮被用户打断时正在执行：

```powershell
$py = 'D:\stagecraft-formal-engine\.venv\Scripts\python.exe'
$env:PYTHONPATH = 'D:\stagecraft-formal-engine'
& $py 'D:\stagecraft-formal-engine\scripts\part1_lock.py' `
  --common 'D:\CodexData\visualizations\2026\10\09\01a12000-d442-7f11-8995-fc98ce5f0d67\formal-real-rerun\analysis\stage_1\formal_part1_merge\primary_common.h5ad' `
  --grid 'D:\CodexData\visualizations\2026\10\09\01a12000-d442-7f11-8995-fc98ce5f0d67\formal-real-rerun\analysis\stage_1\formal_part1_grid' `
  --review 'D:\CodexData\visualizations\2026\10\09\01a12000-d442-7f11-8995-fc98ce5f0d67\formal-real-rerun\artificial_review_fixture.json' `
  --gene STAT1 `
  --out 'D:\CodexData\visualizations\2026\10\09\01a12000-d442-7f11-8995-fc98ce5f0d67\formal-real-rerun\analysis\stage_1\formal_part1_lock'
```

该命令当时被用户中断。该临时状态已在 2026-10-10 后续恢复并完成；后续进度记录中的 lock hash 和 `stopped: locked` 为准，不要再按本节旧建议清理输出。

## 后续开发顺序

按原计划继续，不加入新点子：

1. M6：为 OpenAI-compatible 与 Anthropic adapters 补稳定 HTTP 模拟、弱/错误/恶意响应测试；实现只读 marker evidence 的临时 cluster 候选注释 Proposal，并验证不能写回审阅或正式标签；再覆盖连接配置、授权发送、取消和 Proposal 回填的 Playwright 路径。
2. M6：维护者配置真实端点和凭据后，做一次真实端点验收。未提供端点/key 前不读取环境或仓库外凭据、不把 M6 标为完全验收。
3. M5：真实 GEO 数据在 Studio GUI 跑完 Part 1-5。人工 resolution/cluster 审阅需要真实用户完成；未完成前 fixture 仍只作工程验证。Part 5 R 拟合、source-block holdout 和校准分别按可估计性与计划条件执行。
4. M1：完成速览引擎独立安装、CI/卫生检查、两个 curated 数据集基线复跑和输出对比。
5. M7：完成 GPL 依赖合规方案、一键安装、干净环境、性能压测、备份恢复与发布验收。

每项以原计划验收为准；完成一个顺序项并记录证据后再进入下一项。真实数据和分析输出放在仓库外。

## 已知环境

- Formal engine Python：`D:\stagecraft-formal-engine\.venv\Scripts\python.exe`
- Formal scripts：`D:\stagecraft-formal-engine\scripts`
- 单细胞环境：`D:\miniforge\envs\sc_analysis\`
- R 在 PATH 中；正式 Part 5 仍需按引擎要求验证 R 依赖。
- Studio 目录：`D:\stagecraft-studio`

## 不要做的事

- 不要把旧的 `D:\geo_data\formal_atlas\backup_invalid_walkthrough_20261002` locked atlas 当成这次真实重跑结果。
- 不要把 Quicklook 的 `pbmc3k_raw.h5ad` 结果导入正式审阅。
- 不要把 LODO 写成外部复制。
- 不要提交真实数据、模型、输出目录或本接手文件以外的临时文件。
- 不要在没有用户真实 resolution/cluster 审阅的情况下把 fixture 结果当作最终正式分析证据。

## 2026-10-10 续接进度

Part 1 锁定命令在上轮被用户打断后实际已完成。`formal_part1_lock/lock_record.json` 记录 `stopped: locked`，完整锁定对象 SHA-256 为 `5fe0879d3330f9535bd002e01ca0b4a869e04bbb0bce735423130479095719d1`；对象含 119,413 个细胞、7 个 fixture 标签。标签明确来自 `ARTIFICIAL_REVIEW_FIXTURE`，不是研究者人工审阅。

真实 GEO 锁定对象的 Part 2 survey 成功，生成 14 个 PNG，`rewrote_embedding: false`。Part 3 以全局 cluster 6 的 1,005 个真实细胞作为工程 fixture，从 counts 重算并停在 `awaiting_human_resolution`；未继承全局 UMAP。独立 fixture 锁定 5 个临时子群。Part 4 fixture survey 成功，生成 F04_01-15，forecast 标记为非 verdict，全部 identifiability flag 为 LOW_N。Part 5 prepare 返回 `NOT_ESTIMABLE`：3 个合格 donor、1 个 dataset/source、设计 rank 3/4、rdf 0；未拟合 R 模型，`associated: false`，没有系数。

工程验证：Studio 全测 `170 passed, 2 skipped, 1 warning`；显式配置正式引擎环境变量后两条 Studio→正式引擎集成测试 `2 passed, 1 warning`；Formal Engine `106 passed, 1 warning`；Web typecheck、ESLint、Vitest（3 files / 12 tests）、Ruff、`scripts/check_hygiene.py` 均通过；`git diff --check` 通过（显示既有 CRLF 提示）。Part 2 14 张图和 Part 4 fixture 15 张图均非空。报告位于 `D:\CodexData\visualizations\2026\10\09\01a12000-d442-7f11-8995-fc98ce5f0d67\formal-real-rerun\engineering_validation_report.md`。

剩余事项：真实数据已通过引擎 CLI，但没有在 Studio GUI 中跑大样本全流程；还没有用户真实 resolution/cluster 审阅；Part 5 R 拟合、source-block holdout 和校准均未运行。不得把 fixture 标签当作生物学命名、真实审阅或正式结论。所有真实数据与输出继续留在仓库外。

## 2026-10-10 M6 AI 助手续接

用户要求开始原计划 AI 助手，选择“通用接入”。M6 核心实现在当前未提交工作区：新增 `stagecraft_studio/llm/`、assistant routes、Proposal/provider/LLMCall 表与 Alembic `0004_assistant`；接入 OpenAI 兼容与 Anthropic Messages，包含启动端点探测、发送摘要预览/hash、工具白名单、取消、调用上限、timeout/retry、系统 keyring/进程内存回退、本地解释模式，以及 Proposal 回填研究设计表单。助手不参与 FormalWorker/科学状态；数据库不保存 API key 或原始回复。

截至 2026-10-10，全仓库 pytest、严格 mypy（73 个 Python 文件）、Ruff、`check_hygiene.py`、`git diff --check` 与 OpenAPI 校验通过；Web typecheck、ESLint、12 个 Vitest 和 2 个 Playwright E2E 通过。OpenAPI JSON 与 TypeScript schema 已同步。

M6 尚未完全验收：没有用户指定/可用的真实模型端点和 API key，未做真实服务请求；前端以完整响应显示，streaming 尚未实现。Playwright 已覆盖本地无模型解释、原速览演示、模型状态 mock、发送前授权和只读 `cluster_annotation` Proposal；没有写回按钮。下一步需维护者提供端点/key 做真实服务验收。不要从仓库外文件或环境变量自动猜测/读取 API key。严格遵守原计划权限与科学结论边界。

## 2026-10-10 M6 第一项进度

已完成：

- provider mock 覆盖 OpenAI-compatible 能力探测（文本、工具、结构化、流式）、错误 JSON 和多工具响应拒绝；不访问外网。
- 新增只读 `cluster_annotation` Proposal。它只读取阶段 evidence 中已经存在的 `markers` / `marker_table` / `cluster_markers` 摘要；盲审中不暴露 marker，目标基因从 marker 摘要移除，未授权 cluster 或 marker 直接拒绝。
- 前端将候选名标为“只读候选”，没有写回 cluster 命名/审阅的按钮；`protocol_config` Proposal 仍只能回填研究设计表单。

验证：`tests/test_assistant.py` 6 passed；mypy、Ruff、Web typecheck、ESLint、OpenAPI check 通过；Playwright 两条通过。下一步需维护者提供真实端点/key；若阶段 evidence 没有 marker 摘要，助手必须明确返回不可生成候选，而不是从矩阵临时计算。

## 2026-10-10 下班打断记录（请从这里续接）

用户已明确要求停止，今天不再继续开发。下一次收到继续指令后，从本节恢复。

### 今天实际完成

- `tests/test_assistant.py` 的历史记录已从 `7 passed` 纠正为 `6 passed`。这 6 个测试未新增或修改。
- Studio 全量 Python 回归：`178 passed, 1 warning in 238.00s`，没有 skipped；包含真实正式引擎跨进程集成用例。警告为既有 Starlette/httpx TestClient 弃用提示。
- mypy：`Success: no issues found in 73 source files`；Ruff check：`All checks passed!`；Ruff format：`125 files already formatted`。
- `scripts/check_hygiene.py`、`scripts/export_rule_coverage.py --check`、`scripts/export_openapi.py --check` 均 exit 0。
- Web typecheck、ESLint 通过；Vitest：`3 files / 12 tests` 通过。
- Prettier 检查指出 `web/e2e/demo.spec.ts`、`web/src/panes/Gallery.tsx` 格式问题，已仅对这两个文件执行格式化。之后尚未重新检查；本次尚未重跑 Playwright。前序两条 E2E 的成功记录仍是历史结果。
- 本次未新增功能或测试，没有修改正式引擎、数据或科学审阅记录。仅更新 HANDOFF.md 和格式化上述两个 Web 文件。

### 具体打断点

正在梳理 M6 第一项剩余验收，准备补充测试，尚未开始写测试。最后一个只读命令（读取 `tests/test_review_gates.py`、`db/store.py`、`rules/gates.py`、`llm/tools.py`）被用户中断；可以按需要续读，不必重做此前全部盘点。

已发现的缺口：

1. 当前 `tests/test_assistant.py` 的 HTTP mock 只覆盖 OpenAI-compatible，需要补 Anthropic Messages 探测、请求格式、回复解析及降级验证。
2. Python 服务取消路径尚无专门测试：慢 provider 被取消应记录 `CANCELLED`，不产生 Proposal，也不改变分析/审阅。
3. GUI E2E 目前只有演示路径与只读 cluster 候选展示；缺少真实操作“保存并探测能力”、取消、`protocol_config` 草案转入设计表单的覆盖。
4. marker 授权/盲审/目标过滤的现有覆盖需复核，不要把文档里的概括当成每条边界均已有独立测试。

### 明天续接步骤

1. 读取本节、`AGENTS.md` 和 `docs/milestones.md`，检查 `git status`；保留所有前序未提交改动，不 reset/clean/checkout/stash，不 push。
2. 先补 M6 上述 mock、取消和 GUI 草案回填测试。草案转入表单须断言没有自动调用协议冻结或人工审阅接口。必要时拆测试文件以遵守 Python 400 行、React 300 行上限。
3. 重跑受影响测试和要求的回归，将实际结果更新到 HANDOFF.md、docs/milestones.md、CHANGELOG.md；不要新建过程文档。
4. 继续原计划下一项：M6 真实模型端点验收。当前没有用户提供的服务/模型/key，不能猜测或读取环境和仓库外凭据；真实验收保留未完成状态。
5. 然后 M5 真实 GEO Studio GUI 流程：数据在 `D:\geo_data\formal_atlas`，已有输出在前文 `formal-real-rerun`。人工 gate 必须由用户真实提交；工程测试可使用明确标记 fixture，不能伪装真实审阅。未完成人工门禁时只推进独立工程工作，不能自动选 resolution、KEEP/DELETE 或命名。
6. 后续保持既有顺序：M1 安装/CI/卫生/两个 curated 基线；M7 许可、安装、性能、备份与发布。

### 实际可用命令与环境

本次 shell 的 PATH 没有 `uv`，用项目 `.venv` Python 执行等价命令成功；pnpm 和 Node 可用。终端默认沙箱启动出现 `helper_unknown_error: setup refresh had errors`，经工具升级执行后正常，并非测试失败。

在 `D:\stagecraft-studio` 执行（没有读取模型凭据）：

```powershell
$env:STAGECRAFT_FORMAL_SCRIPTS = 'D:\stagecraft-formal-engine\scripts'
$env:STAGECRAFT_FORMAL_PYTHON = 'D:\stagecraft-formal-engine\.venv\Scripts\python.exe'
$env:Path = 'D:\miniforge\envs\sc_analysis\Library\bin;' + $env:Path
& '.\.venv\Scripts\python.exe' -m pytest
& '.\.venv\Scripts\python.exe' -m mypy
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m ruff format --check .
& '.\.venv\Scripts\python.exe' scripts/check_hygiene.py
& '.\.venv\Scripts\python.exe' scripts/export_rule_coverage.py --check
& '.\.venv\Scripts\python.exe' scripts/export_openapi.py --check
pnpm -C web typecheck
pnpm -C web lint
pnpm -C web test
pnpm -C web exec prettier --check .
pnpm -C web e2e
```

所有测试进程本次已结束；只有最后的只读命令被打断。数据、数据库、日志和输出保持仓库外，不复制进代码仓库。

### 打断时工作区快照

已有大量前序未提交改动，快照仅供核对，并不表示全部改动由今天产生。

```text
 M CHANGELOG.md
 M README.md
 M docs/milestones.md
 M pyproject.toml
 M scripts/check_hygiene.py
 M scripts/start-studio.cmd
 M stagecraft_studio/api/app.py
 M stagecraft_studio/api/review_routes.py
 M stagecraft_studio/db/gallery.py
 M stagecraft_studio/db/migrations/env.py
 M stagecraft_studio/domain/protocol_form.py
 M stagecraft_studio/engine/formal_args.py
 M stagecraft_studio/engine/registry.py
 M stagecraft_studio/rules/gates.py
 M stagecraft_studio/rules/scientific_status.py
 M stagecraft_studio/worker/jobs.py
 M stagecraft_studio/worker/publish.py
 M tests/test_formal_launch.py
 M tests/test_formal_real_chain.py
 M tests/test_formal_real_pipeline.py
 M tests/test_formal_worker.py
 M tests/test_gallery.py
 M tests/test_protocol_form.py
 M tests/test_start_studio.py
 M uv.lock
 M web/e2e/demo.spec.ts
 M web/index.html
 M web/openapi.json
 M web/src/App.tsx
 M web/src/api/client.ts
 M web/src/api/schema.ts
 M web/src/app.css
 M web/src/panes/Assistant.tsx
 M web/src/panes/FormalDesk.tsx
 M web/src/panes/Gallery.tsx
 M web/src/panes/GalleryCard.tsx
 M web/src/panes/ProtocolForm.tsx
 M web/src/panes/StageWorkspace.tsx
 M web/src/panes/TopBar.tsx
 M web/src/panes/WorkspaceResults.tsx
 M web/src/text/chrome.ts
 M web/tests/shell.test.tsx
?? HANDOFF.md
?? stagecraft_studio/api/assistant_routes.py
?? stagecraft_studio/db/assistant_models.py
?? stagecraft_studio/db/migrations/versions/0004_assistant.py
?? stagecraft_studio/llm/
?? stagecraft_studio/worker/formal_defaults.py
?? tests/test_assistant.py
?? tests/test_formal_defaults.py
?? tests/test_gallery_status.py
?? web/src/panes/AssistantConnection.tsx
?? web/src/panes/AssistantParts.tsx
?? web/src/proposal_store.ts
```

## 2026-10-11 M6 第一项补充完成

按上一节顺序完成并验证：

- 新增 `tests/test_assistant_providers.py`，覆盖 OpenAI-compatible 与 Anthropic Messages provider mock、请求格式、能力探测、错误 JSON、多工具响应、schema 拒绝和服务级取消。
- `tests/test_assistant.py` 保留核心助手/Proposal 测试，331 行；provider 测试文件 299 行，均通过文件长度卫生门禁。
- `web/e2e/demo.spec.ts` 新增助手调用取消和 `protocol_config` 草案回填 E2E。回填只切换到研究设计表单并填值；冻结接口调用次数断言为 0。
- Playwright 最终结果：`4 passed (9.7s)`；Web Vitest：`3 files / 12 tests`；typecheck、ESLint、Prettier 均通过。
- Studio Python 全量最终结果：`182 passed, 1 warning in 209.02s`。警告仍为 Starlette/httpx TestClient 弃用提示。
- mypy、Ruff check、Ruff format、`scripts/check_hygiene.py`、`scripts/export_rule_coverage.py --check`、`scripts/export_openapi.py --check` 均通过。

M6 第一项已完成，下一项仍未开始：原计划是 M6 真实模型端点验证。当前用户没有提供 endpoint、model 或 API key；不能从环境变量、仓库外文件或系统凭据猜测/读取。前端仍按完整响应展示，streaming token UI 未实现。真实端点、凭据和实际模型返回仍未验收。

下一次继续顺序：

1. 先核对本节、`AGENTS.md`、`docs/milestones.md` 和 `git status`，不要 reset/clean/checkout/stash/push。
2. 如用户提供真实服务配置，只做一次 OpenAI-compatible 或 Anthropic 真实端点验收，记录能力探测、授权发送、错误隔离和 Proposal 权限边界；API key 不写入日志、数据库或文档。
3. 若仍无真实端点，保持 M6 真实服务为未验收，进入 M5：用 `D:\geo_data\formal_atlas` 在 Studio GUI 跑真实 Part 1–5。真实 resolution/cluster 审阅必须由用户提交；`ARTIFICIAL_REVIEW_FIXTURE` 只能作工程 fixture。Part 5 依据真实 donor/condition/source-block 可估计性决定是否拟合。
4. 之后按原计划进入 M1 速览引擎安装/CI/卫生/两个 curated 基线，再进入 M7。

## 2026-10-11 M5 续接尝试

- M6 第一项补充完成后，按原顺序准备进入 M5 真实 GEO Studio GUI 走查。
- 已核对真实数据入口：`D:\geo_data\formal_atlas\data.h5ad`、16 个 library 清单和 `walkthrough_scripts/step1_design.mjs`。走查只计划冻结研究设计并建立 StageRun，不会自动提交 resolution/cluster 人工审阅。
- 真实 Studio 启动命令在当前自动审批窗口超时，未能可靠启动；随后只读检查确认 8795 端口没有监听，不能把 GUI 走查记为成功。
- `D:\geo_data\formal_atlas\screenshots\01_research_design_frozen.png` 是仓库外既有截图，时间早于本次尝试，不能作为今天真实 GUI 验收证据。没有复制或修改真实数据、数据库或输出。

下一次继续时：先重新启动 Studio（数据库建议使用仓库外的新路径，如 `D:\geo_data\formal_atlas\studio-gui-20261012.sqlite`），确认 `http://127.0.0.1:<port>/` 能访问，再执行 `step1_design.mjs`。冻结后停在 Review Center，等待用户真实选择 resolution、提交 cluster KEEP/DELETE 与命名；不得自动执行 `step2_review.mjs` 中的示例命名，除非用户明确确认这些是本次真实人工审阅。

## 2026-10-11 M5 Part 1 真实 GUI 走查完成至人工门禁

- 使用仓库外数据库 `D:\geo_data\formal_atlas\studio-gui-20261011.sqlite` 和单个 Studio worker，在 `http://127.0.0.1:8795/` 完成真实研究设计 GUI；16 个 library、目标基因 `STAT1`、Harmony `dataset`、真实数据路径冻结成功。
- 协议 hash：`157e94e4b433171a44176ed051edbd22db0af8372e3cfc2ed352b5967944deec`。StageRun `#1` 保持 `READY`。
- 真实 Part 1 load 最终 16/16 `COMPLETED`；真实 QC 最终 16/16 `COMPLETED`；merge 任务 `#43` `COMPLETED`；resolution grid 任务 `#44` `COMPLETED`。
- grid 真实概览：0.2=7 clusters，0.3=7，0.4=7，0.5=7，0.6=9，0.8=11，1.0=12，1.2=14，1.5=17。`grid_record.json` 明确 `selected_leiden_resolution: null`、`stopped: awaiting_human_resolution`。
- GUI 审阅中心只读展示真实 9 档分辨率和 cluster 表，截图在 `D:\geo_data\formal_atlas\screenshots\11_real_review_resolution_wall.png`。没有选择 resolution、没有提交 KEEP/DELETE、没有命名、没有提交审阅；科学状态仍为 `NOT_REPORTED`，校准仍为 `NOT_ESTABLISHED_FOR_THIS_ANALYSIS`。
- 途中曾误启动两个共用数据库的 Studio worker，导致 Windows HDF5 文件锁冲突，出现 10 个历史 `OUTPUT_CONTRACT_MISSING` 任务。独立诊断确认数据和正式引擎可读；停止双 worker 后以单 worker 顺序重入队，9 个此前失败 library 全部成功。旧失败记录保留作审计，不当作最终分析结果。
- 本次服务已停止，8795 不再监听；真实数据库、日志、截图和分析产物均留在仓库外。

下一次继续：必须由用户在 GUI/服务端真实选择 resolution 并提交 cluster KEEP/DELETE 与命名；不得使用 `step2_review.mjs` 的示例 PBMC 名称替代这次真实人工审阅。人工 gate 完成后，再按注册任务执行 Part 1 lock、Part 3 和 Part 2/4/5；Part 5 仍须依据真实 donor/condition/source-block 可估计性决定是否拟合。

## 2026-10-11 术语与双语界面分支

- 用户要求先暂停试用，建立独立分支修正生信术语并增加英文界面；当前分支：`feat/bioinformatics-terminology-i18n`。
- 已加入持久化界面语言选择：顶栏 `界面语言 / Interface language`，支持中文与 English，偏好存于浏览器 `localStorage`，默认中文。切换不修改 API 值、规则 ID、科学状态码、审阅凭据或分析数据。
- 规范化的中文显示术语包括：`冻结研究方案`、`Harmony 整合变量`、`最低检出基因数（宽松 QC 阈值）`、`聚类分辨率`、`细胞群（cluster）`、`保留（KEEP）`、`剔除（DELETE）`、`细胞群命名`、`提交科学审阅`、`盲法状态`、`结果图集`、`规则检查`、`模型拟合` 等。
- 双语覆盖了顶栏、速览表单、正式分析工作区、科学审阅、Part 3 停点、研究方案表单、结果图集、NOT_ESTIMABLE 提示、AI 助手和连接设置。服务器返回的自由文本证据/科学状态仍按原值显示，避免翻译改变审计含义。
- 验证：Web typecheck、ESLint、Prettier、Vitest `3 files / 13 tests`、Playwright `4 passed`；Python hygiene、Ruff format、`git diff --check` 通过。此次只改界面显示层和测试断言，没有触碰真实 StageRun、数据库或正式分析产物。

交互式试用：当前 Studio 单 worker 仍可通过 `http://127.0.0.1:8795/` 使用真实 GEO StageRun；用户可以先切换语言检查术语，再进入正式分析审阅。不要在此分支上自动提交 resolution/cluster 科学判断；发现术语或交互问题时继续在本分支记录并修正。

## 2026-10-11 正式分析工作区可读性改进

- 用户反馈正式分析工作区信息层级不够清楚。本轮只调整前端显示层，没有修改 API、审阅规则、科学状态、StageRun、数据库或分析产物。
- 正式分析页新增页面上下文标题与 Part 1–5 范围提示；审阅页新增科学审阅说明、运行选择器分组和两个明确停点标题。
- 工作区输入页改为键值摘要布局，路径与 SHA-256 使用可换行代码块；结果页将科学状态、产物清单、规则检查和任务日志分成可扫读区块，长 JSON 限制在滚动区域内。
- 审阅页将科学状态、聚类分辨率、细胞群决策和审阅依据分开；同时修正“审阅依据”输入框此前错误显示为“聚类分辨率”的标签问题。中英文映射同步更新。
- 浏览器只读验证使用仓库外数据库 `D:\geo_data\formal_atlas\studio-gui-20261011.sqlite`；服务当前仍在 `http://127.0.0.1:8795/` 运行，便于用户继续交互。真实审阅仍停在人工门禁，没有提交 resolution、KEEP/DELETE 或命名。截图：`D:\geo_data\formal_atlas\screenshots\12_review_readability.png`。
- 验证通过：Web `typecheck`、ESLint、Vitest `3 files / 13 tests`、Prettier、生产 `pnpm build`、`git diff --check`；Impeccable mechanical detector 无新增问题。980px 窄视口实测无横向溢出；顶栏在窄屏自动换行到第二行，正式分析内容保持可读。

下一次继续：保持当前分支 `feat/bioinformatics-terminology-i18n`，优先收集用户对正式分析工作区术语、停点提示和表格操作的交互反馈；继续禁止自动提交真实 resolution/cluster 科学判断。

## 2026-10-11 科学状态可读化

- 用户反馈正式分析中的“科学状态”说明过于抽象。本轮只改前端解释层：保留服务器返回的状态码和原始 `limits`，增加面向使用者的结论标题、短解释和校准边界提示。
- `NOT_REPORTED`、`FROZEN_PASS`、`FITTED`、`NOT_ESTIMABLE`、`INVALIDATED` 均有中英文可读映射；未知状态仍显示原码并提示以原始限制为准。
- 审阅中心和阶段工作区结果页都已使用同一套解释映射；关联支持、Limma 主张改为“有/无（Yes/No）”，不再直接显示 `True/False`。
- 新增中英文映射测试；Web Vitest 当前 `14 passed`，typecheck、ESLint、Prettier、生产 `pnpm build`、`git diff --check` 均通过。
- 当前临时 Studio 仍在 `http://127.0.0.1:8795/`，使用仓库外数据库 `D:\geo_data\formal_atlas\studio-gui-20261011.sqlite`；未提交任何真实科学审阅判断。
- 浏览器最终实测截图：`D:\geo_data\formal_atlas\screenshots\16_scientific_status_readable.png`。`NOT_REPORTED`、校准、留一来源块、Part 4 和 NOT_ESTIMABLE 均已显示为人话解释，同时保留原始 `NOT_REPORTED` 状态码。

## 2026-10-11 科学状态文案精简

- 用户指出“科学状态”说明仍有明显 AI 味且校准/关联/Limma 标签粘连。本轮按“结论—状态字段—解读边界”重排：`NOT_REPORTED` 显示为“科学审阅尚未完成”，说明具体指出分辨率和细胞群审阅尚未提交。
- 校准、关联支持、Limma 主张改为分列字段；Limma 使用“未提出”，避免把无主张写成分析失败。校准仅保留一次说明，删除重复限制句。
- 限制改写为：来源块留一用于检查稳健性但不能替代独立队列验证；Part 4 是目标基因表达描述而非模型拟合；设计信息不足时无法估计效应，但不等于证明效应不存在。中英文同步调整。
- Web Vitest `14 passed`，TypeScript、ESLint、Prettier、生产构建通过。实时浏览器确认审阅页和结果页均按预期分段；截图：`D:\geo_data\formal_atlas\screenshots\17_scientific_status_rewrite.png`。

## 2026-10-11 Part 3 图库入口修复

- 用户询问图库缺少 Part 3。真实数据库 `studio-gui-20261011.sqlite` 的 StageRun #1 只有 Part 1 load/QC/merge/grid 任务和产物；因 Part 1 人工审阅尚未提交，Part 3 尚未执行，所以该运行当前确实没有 Part 3 图。
- 同时发现产品缺陷：图库后端没有把 `formal_part3_recluster` 产物分类为 Part 3，前端筛选也缺少 Part 3 入口。已补分类、双语筛选项和“当前运行尚未生成 Part 3 图像”的空状态说明。
- `tests/test_gallery.py` 加入 Part 3 resolution overview fixture，验证后端分类为 Part 3、panel id 为 F03_grid，并确认盲审时仍展示 Part 1/3 而过滤 Part 2。
- 验证：图库 Python 测试 `5 passed`；Web Vitest `14 passed`、typecheck、ESLint、Prettier、生产构建通过。真实浏览器验证 Part 3 按钮出现且当前运行显示尚未生成提示。没有修改真实 StageRun 或提交审阅判断。

## 2026-10-12 Part 1 分轮审阅流程修复

- 用户反馈无法选择 Leiden 群、查看表格、删除低质量群后进入下一轮并在稳定轮命名。本轮修复了提交后前端停点状态不同步、切换 Run 残留临时分辨率，以及表格/重聚类/锁定任务失败后不可重试的问题。
- 后端按顺序执行：选择 resolution 后自动生成正式 marker/QC 表；表格完成前拒绝群审阅；首次只提交 KEEP/DELETE；若有 DELETE，从 retained raw counts 重算 HVG、PCA、Harmony、Leiden 并进入下一轮；无 DELETE 时单独命名；命名后才锁定 Part 1。正在运行时的重复排队会复用活动任务。
- 增加 `tests/review_helpers.py` 和 `tests/test_part1_review_workflow.py`，测试表格门禁、去留/命名分离、重复命名拒绝和 DELETE 后 round 1 流程；更新锁定与端到端 fixture。
- 验证：Part 1 审阅/锁定/链路回归 16 passed；Web 14 tests passed；类型、Lint、Prettier、卫生检查通过。生产 bundle 已重建并部署。
- 真实 Studio 在 `http://127.0.0.1:8795/` 使用仓库外数据库运行。只读检查确认 StageRun #1 仍为 READY、CHOOSE_RESOLUTION，未写入人工科学判断。
- 真实 Formal Engine 端到端回归还发现并修复了一个边界：某档 Leiden 只有一个群或没有可排名 marker 时，Scanpy 可能返回不含 `cluster` 列的空 marker 表。引擎现在保留空 marker 表头并照常导出逐群 QC；正式引擎 review-table 测试 2 passed，Studio 真实端到端测试通过。

下一步由用户选择真实 resolution；待 marker/QC 表生成后提交 KEEP/DELETE，再按结果进入下一轮或单独命名。不要替用户提交科学判断。

## 2026-10-12 Part 1 表格质量修复（进行中）

- 用户真实试用 `resolution=0.5` 后发现逐群 QC 大量为空、marker 拼在一个单元格中导致无法阅读。本轮已修正 Formal Engine：兼容合并对象实际字段 `n_genes/pct_mt/pct_hb`，并在缺失时从 `counts` 与基因符号补算核糖体比例、Top 50 基因比例和基因/UMI 复杂度。
- 新增 `selected_markers.csv`：一行一个 cluster-gene，包含 rank、logFC、群内/群外检出率、检出率差、marker 证据等级和分级依据。等级只用于人工筛选，不作细胞类型证明或供体层面推断。Scrublet 未随对象保存时标为 `not_saved`，不使用替代值冒充。
- Studio API 同时返回 `qc` 与 `markers`；旧的 `selected_top20_by_cluster.csv` 仍可兼容读取，但新界面拆为“QC 汇总”和“Marker 证据”两个视图，并支持按 cluster 筛选。QC 表移除长 marker 文本，增加 Scrublet 数据状态和明确的 QC 提示。
- 已更新 Formal Engine 输出契约、测试 fixture、中英文文案和 CSS。Web TypeScript 检查通过；Formal Engine 文件 AST 语法检查通过。完整 Python 回归尚未完成：当前系统 pytest 的 `_ssl` DLL 被拒绝加载，Studio 虚拟环境指向已不存在的 Python 3.10；`sc_analysis` 导入 Scanpy 测试进程异常缓慢。
- 真实 Run #1 原有的 0.5 审阅表已清理，resolution 决定已回退；现在还没有新版审阅表。用户在新版 Studio 重新选择 resolution 后会重算表格。不要替用户提交 cluster KEEP/DELETE/命名。

## 2026-10-12 下班交接

- 今天已完成旧试用状态清理。真实数据库 `D:\geo_data\formal_atlas\studio-gui-20261011.sqlite` 中的 StageRun #1 当前为 `READY / CHOOSE_RESOLUTION`，`active_round=0`，没有选定 resolution，没有 `formal_part1_review_tables` 任务，没有 review-table artifact，也没有 resolution、cluster KEEP/DELETE 或命名记录。
- 新版 Studio 当前运行在 `http://127.0.0.1:8796/`，API 已验证返回 `review_state=CHOOSE_RESOLUTION`、`review_tables.available=false`，并包含新版 `markers` 字段。浏览器里原来的 `http://127.0.0.1:8795/` 是旧端口/旧进程，不要用它判断本轮结果。
- 明天第一步：打开 `http://127.0.0.1:8796/`，在正式分析中选择一个 resolution，等待新版 `formal_part1_review_tables` 完成，然后分别检查“QC 汇总”和“Marker 证据”两张表。确认表格可读后，再由用户决定是否 KEEP/DELETE；不要自动提交科学判断。
- 当前修复涉及 Formal Engine 的 QC 字段兼容与 counts 补算、`selected_markers.csv`、Studio API 的 `qc + markers` 契约，以及右侧表格双视图。Web typecheck 和生产构建已通过；Python 完整回归仍受本机 Python/DLL 环境限制，明天如需验收先使用 `D:\miniforge\envs\sc_analysis` 和单独的临时 Studio 环境。
- 临时 Studio 运行环境在仓库外 `D:\geo_data\formal_atlas\studio-venv-314`。不要删除真实分析目录、SQLite、WAL 文件或 `studio-gui-20261011-before-reset-20261012.sqlite` 存档；后者是 WAL 不完整副本，仅作记录，不能用于恢复。
