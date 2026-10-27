# 里程碑

任务书第 15 节是里程碑定义。这里只记录切片状态。

CI 现状：Studio `740dd15` 的 Actions 成功过，6 个 job（Python 3.10 与 3.11 的 ubuntu 和 windows，web 的 ubuntu 和 windows）。`740dd15` 之后的提交还没推送，那些提交的 CI 没跑。Playwright 不在 Actions 里。下面各节里写「见文首的 CI 现状」的，当时那一节结束时 CI 还没跑，后来的结果以这一段为准。

## M0-A 仓库骨架

状态：本机检查通过，尚未提交。见文首的 CI 现状。证据在 skill 仓库本地交接文件，不在本仓库重复贴日志。

## M0-B 只读盘点

状态：本机盘点已写入 `capability-map.md`。规模建议在 `architecture.md`，仍是待确认。见文首的 CI 现状。

## P1 速览命令行雏形

状态：本机测试通过。`quicklook_run` 停在 phase03。

## P2 本地速览页面

状态：本机测试通过。`serve` 只监听 127.0.0.1。浏览器打开了表单。

## P3 结果页

状态：本机测试通过。结果页显示运行状态、速览标记和 `99_logs` 日志尾部。

## P4 引擎路径预填

状态：被单元 A 取代。这两个路径仍来自启动参数或环境变量，页面只显示，不能提交。

## P5 本地基因集门

状态：本机测试通过。有 `LOCAL_GMT` 文件才跑到 phase05，否则停在 phase03。判断在 `engine/quicklook_scope.py`。pytest 46 项通过。

## M1 速览引擎产品化

状态：已开始。干净目录是 `D:\scrna-target-engine`。已去掉在线富集和 `hadha_source`，报告写明启发式分辨率。引擎测试 13 项通过。`uv sync` 因 annoy 构建超时未完成。CI 与卫生检查还没有。

## M0-C 规模确认

状态：不再单独暂停。施工数字见 `architecture.md`。压测仍未做。

## 单元 A 安全与正确性

状态：本机已改。表单不能指定要执行的程序。失败运行仍带 quicklook 标记。输入格式写入 `INPUT_FORMAT`。`quicklook_inspect` 列出 h5ad 的 obs 列。非空输出目录会拒绝。引擎 `BATCH_COLUMN` 默认值只在 `config_contract.py`。见文首的 CI 现状。

## 单元 B 后台运行与结果状态

状态：本机已改。`POST /quicklook` 立即跳到 `/runs/<id>`。同一时间只能有一次速览。取消会停掉进程树。结果页分开显示引擎、输入和图质量。`templates.py` 没有改。见文首的 CI 现状。

## 单元 D 引擎卫生检查和 CI

状态：在 `D:\scrna-target-engine`。本仓库没有改。

## 单元 E1 React 界面

状态：本机已改。`/api` 提供运行、步骤、文件、表格和脚本源码。页面是三栏。日志、代码、参数和图片在 React 里。`templates.py` 已删除。见文首的 CI 现状。

## 单元 E2 预览、表格、环境和演示

状态：已提交 `7d8a06b`。文件树点开后在中栏预览。CSV 搜索和排序走分页接口。环境页由后端给出通过或不通过。演示数据由引擎脚本现写，不提交 h5ad。见文首的 CI 现状。

`6746531` 拦住了表格向总行数之外要数据。3 行的 `genes.csv` 不再反复请求 `offset=3`。

## 界面返修

状态：已提交。字号只留 12/14/16/20/24 px，圆角只留 8 和 12，阴影两级，一个强调色。面板文案在 `web/src/text/chrome.ts`。产物质量用服务端 `quality_status`。助手只写「未接入」。`prettier --check` 通过。见文首的 CI 现状。

## 单元 E3 方法、复现包、对比和通知

状态：本机已改。方法段落由服务端模板生成，写明细胞水平、探索性、临时标签。复现包是 zip，含 config、argv、引擎信息，不含数据。两次运行并排对比参数、细胞数、cluster 数和图质量。运行从进行中变成结束时，已授权的浏览器可以发桌面通知。见文首的 CI 现状。

## 单元 F1 Host 头

状态：本机已改。`TrustedHostMiddleware` 只允许 `127.0.0.1` 和 `localhost`。`Host: evil.example` 请求 `/api/bootstrap` 得到 400，响应里没有令牌。见文首的 CI 现状。

## 单元 F2 合成矩阵四阶段

状态：在速览引擎 `d5f27cd`。Studio 没有改运行逻辑。80 细胞、250 基因的合成矩阵在断网时跑完四个阶段。图质量是拒绝。见文首的 CI 现状。

## 单元 F3 默认基因集

状态：留空时下载人和鼠的 Hallmark 与 GO Biological Process（MSigDB 2026.1）。KEGG 不下载，由用户导入 GMT。缓存文件是 `%LOCALAPPDATA%\stagecraft-studio\gene-sets\{species}-2026.1.gmt`。离线且没有缓存时，页面提示改填本地 GMT，不留下失败的运行。自己填的 GMT 优先。基因列表不外发。测试不联网。见文首的 CI 现状。

## 单元 F4 10x h5

状态：`.h5` 记为 `h5`，引擎用 `scanpy.read_10x_h5`。测试用合成矩阵。见文首的 CI 现状。

## 单元 F5 汇总图

状态：`06_portfolio` 的清单提供每一格的位置。页面点格打开原图，同名表在中栏打开。见文首的 CI 现状。

## 单元 F6 启动脚本

状态：`scripts/start-studio.cmd` 只调用 uv 和 pnpm。`@echo off` 之后执行 `chcp 65001`。脚本用 CRLF，否则 UTF-8 代码页会把后面的命令拆开。中文提示按 UTF-8 显示。环境页每一项不通过都带修复说明。见文首的 CI 现状。

## 单元 F7 真实数据

状态：GSE159677 已从页面跑完，图质量通过。AS/PA 分组是推断的，未经作者元数据核实。这次运行不能当作 case/control 方向已经核实的证据。说明在输出目录 `00_metadata/group_assignment.txt`。见文首的 CI 现状。

## 单元 F8 Playwright

状态：一条路径：打开页面、运行演示、看到结果、打开一张图、下载复现包。用假引擎，不跑 1600 细胞。见文首的 CI 现状。

## G0 专有声明

状态：已提交 `22a55a6`。根目录 `LICENSE` 是 `Copyright 2026 GuomingLin. All rights reserved.`。产品闭源。GitHub 仓库的可见性由维护者在网页上确认为私有之前，不推送。

## G4 数据库与协议冻结

状态：已提交 `c455493`。Alembic `0001_core` 建了 Project、ProtocolVersion、StageRun、Job、ReviewDecision、Artifact、RuleResult、AuditEvent。冻结后算协议 hash。输入或协议变了，旧 stage run 被 `PROTOCOL_HASH_MATCH` 阻断。登记了 `formal_part1_load`、`formal_part1_qc`、`formal_part1_merge`、`formal_part1_grid`。速览的 `run_status.json` 没有迁。

## G5 人工 gate

状态：已提交 `2137532`。分辨率、cluster KEEP/DELETE、盲审、看过速览就解盲、DELETE 后不能沿用旧 UMAP、上游变更让下游只读，都在服务端。直接调 API 也走这些检查。`docs/rule-coverage.md` 由脚本生成。

## G6 审阅中心

状态：已提交 `6aa352b`，测试 `1f0d309`。正式分析页是分辨率图墙和 cluster 表。从速览带入只保留数据路径、字段映射和目标基因。Playwright 仍只有速览那一条。

## M5 科学状态

状态：已提交 `3e8c85c`。审阅中心的科学状态由服务端从已保存记录算出。请求不能带 `scientific_status`。校准状态保持 `NOT_ESTABLISHED_FOR_THIS_ANALYSIS`。`associated` 不能被请求抬成 true。

## M5 研究设计表单

状态：已提交 `1126592`。字段来自 `GET /api/protocol/form`。冻结走 `POST /api/protocol/freeze`。Harmony 必须含 `dataset`，拒绝 `donor_id`、`condition`、`disease`、`cell_type` 和目标基因。

## P14 规则覆盖落表

状态：已提交 `9eb24ba`。FormalWorker 中在任务发布后评估引擎输出契约与日志，写入 `RuleResultRow`（覆盖 `INPUT_COUNTS_VALID`、`PER_LIBRARY_QC`、`DOUBLET_FAILURE_EXPLICIT`、`TARGET_MEASURED_IN_COMMON_SET`、`DESIGN_ESTIMABLE` 5 项核心规则）。`catalog.py` 与 `docs/rule-coverage.md` 全部更新并通过单元测试。

## P15 阶段工作区

状态：已提交 `d433d62`。后端实现 `GET /api/stage-runs/{run_id}/workspace`，聚合输入、参数、结果、检查、日志 5 个页签；连接 Part 2-5 证据入库（`StageRun.evidence_json`）；前端拆分 `StageWorkspace.tsx` 与 `WorkspaceResults.tsx`，严格满足 300 行卫生上限。

## P16 正式分析图库

状态：基础图库已提交 `61fb4b3`。后续补齐 Part 3：`formal_part3_recluster` 图像现归类为 Part 3，图库提供中英文筛选；当前 StageRun 尚未运行 Part 3 时会明确提示图像尚未生成。回归测试验证 Part 3 resolution overview 被归到 `F03_grid`，且盲审仍保留 Part 1/3、过滤 Part 2。见 `tests/test_gallery.py`。

## M4 验收

| 条款 | 状态 | 说明 |
| --- | --- | --- |
| 人工 gate 跳不过去，直接调 API 也不行 | 通过 | `tests/test_review_gates.py`，请求模型 `extra=forbid`，无令牌 401 |
| 旧审阅不能用于新聚类 | 通过 | `test_old_cluster_review_does_not_apply_to_new_ids` |
| Scrublet 失败路径有测试 | 通过 | 正式引擎 `tests/test_part1_qc.py`，pytest 通过 |
| 新引擎 CI 在 ubuntu 和 windows 通过 | 未满足 | 正式引擎为私有、闭源仓库，尚无远端，CI 未真实运行（需要私有远端，GitHub Actions 对私有仓库消耗额度，由维护者决定是否启用） |
| 从速览开始只带入路径、字段映射和基因 | 通过 | `test_quicklook_carry_omits_labels_and_resolution` |
| 合成多 library 数据从 Part 1 走到 Part 3 一轮 | 通过 | `tests/test_formal_real_chain.py` 与 `tests/test_formal_real_pipeline.py` 均使用真实正式引擎脚本端到端执行通过（覆盖 Part 1 加载→QC→合并→网格→审阅→Part 3 重聚类及后续，依赖本地正式引擎环境变量，CI 环境未配置时自动 skip） |

## M5 验收

| 条款 | 状态 | 说明 |
| --- | --- | --- |
| 同一主线在 GUI 里跑通 | 部分满足 | 真实 GEO 数据已在 Studio GUI 完成研究设计冻结、16/16 load、16/16 QC、merge 与 resolution grid，并在审阅中心停到真实人工 resolution/cluster gate；真人试用尚待用户完成 resolution/cluster 决策，之后再继续 Part 1 lock、Part 3、Part 2/4/5 |
| skill 仓库已有科学回归不退化 | 通过（需 PATH 含 sc_analysis\Library\bin） | Windows 下需将 `D:\miniforge\envs\sc_analysis\Library\bin` 加入 PATH 解决 `libiomp5md.dll` 依赖，加入后全量 pytest 125 passed，零退化 |
| 不可估计和校准限制在界面和报告中保留 | 通过 | 报告、审阅中心、阶段工作区、图库页均保留 NOT_ESTIMABLE 槽位与校准限制；盲审门禁在原图下载（`/artifacts/raw`）与图库（`/gallery`）已补齐（审阅前/盲审期过滤目标基因产物，严禁 `.studio/` 内部访问），已在 `test_formal_real_pipeline.py` 中端到端核验 |

## 剩余工作

- 真人交互试用当前 Studio；收集并修复用户指出的术语和操作可读性问题。用户真实提交 resolution/cluster 审阅前，不继续真实 StageRun 的下游阶段。
- 大样本真实数据在 Studio GUI 中从人工 resolution/cluster gate 继续完成 Part 1–5；真实设计、load、QC、merge、grid 已完成，当前没有 Part 3 任务。
- 正式引擎私有远端仓库配置（由维护者创建与推送，GitHub Actions 对私有仓库消耗额度，由维护者决定是否启用）。
- GPL 依赖与闭源分发的许可风险，M7 打包前必须解决（替换实现或取得合规方案）。涉及：harmonypy（GPL-3.0，用于 Part 1 合并批次校正 formal_part1_merge）、leidenalg（GPL-3.0，用于 Part 1 分辨率网格聚类 formal_part1_grid 与 Part 3 重聚类 formal_part3_recluster）、python-igraph（GPL-2.0-or-later，leidenalg 的底层图计算依赖）。
- M6（可选 AI 助手，只读证据与代码解释，不生成新标签与推断结论）。
- M7（打包与部署）。

## M6 AI 助手

状态：核心闭环已实现，真实外部端点待维护者配置后验证。右侧助手支持本地字段/规则/阶段解释、OpenAI 兼容与 Anthropic Messages 配置、能力探测、摘要发送预览、显式发送确认、有限工具调用与结构化 `Proposal (DRAFT)`。Proposal 只能回填正式研究设计表单，仍须用户检查并通过原有校验；助手不会冻结协议、提交审阅或改变科学状态。服务端只持久化不含 key 的模型设置、调用 hash、来源引用、状态/用量和草案；密钥进入系统凭据库，失败则仅留在进程内存。M6 本地模式已有 Playwright 覆盖；全量 Python 测试、mypy、Ruff、hygiene、OpenAPI、Web typecheck/ESLint/Vitest 和 Playwright 均通过。

已完成 M6 第一项中的 provider HTTP mock、错误/恶意响应拒绝，以及从授权 marker evidence 生成只读 `cluster_annotation` Proposal；目标基因、盲审 marker、未授权 cluster/marker 均被服务端过滤或拒绝，候选不会写回正式标签。补充覆盖了 Anthropic Messages 请求/解析、服务级取消，以及 GUI 取消和 `protocol_config` 草案回填（只进入研究设计表单，不自动冻结或提交审阅）。见 `tests/test_assistant.py` 与 `tests/test_assistant_providers.py`。

验证：Studio Python 全量 `182 passed, 1 warning`；mypy、Ruff、hygiene、OpenAPI、Web typecheck/ESLint/Vitest（3 files / 12 tests）、Prettier 和 Playwright（4 tests）均通过。剩余：维护者提供端点后进行真实服务验证；前端仍为完整响应，未实现流式展示。真实模型服务、key 和人工审阅仍未验收。

## 当前执行顺序

1. 用户在 `http://127.0.0.1:8795/` 真人完整试用；依据即时反馈修复界面并继续同步术语。
2. 用户亲自完成真实 Part 1 resolution 与 cluster KEEP/DELETE/命名审阅；严禁用 fixture 或模型代交。
3. 依注册任务继续 Part 1 lock、Part 3、Part 2/4/5；Part 5 根据真实设计可估计性决定是否拟合。
4. M6 真实端点验收待维护者提供服务和凭据；不阻塞当前试用。
5. 再按原计划进入 M1 速览引擎安装/CI/卫生/curated 基线，之后进入 M7 许可、安装、性能和备份恢复验收。

2026-10-11 试用前验证：图库后端 `tests/test_gallery.py` 为 `5 passed`；Web Vitest 为 `14 passed`，typecheck、ESLint、Prettier、生产构建通过。Studio 真人服务使用仓库外 SQLite；本次仅只读核查，StageRun #1 仍为 `READY`，无 Part 3 job，无人工审阅变更。
### 真人试用：Part 1 群体审阅表格（2026-10-11）

右侧面板新增“表格”入口，读取正式引擎生成的逐群 QC 与 marker 摘要。当前真实运行尚未到生成这些表的阶段，因此显示受控空状态；不会用估算值替代正式产物。QC 复核提示仅供人工审阅，不改变审阅门禁。

## 2026-10-12 Part 1 分轮人工审阅流程

状态：工程修复完成，真实人工判断仍等待用户。选择 resolution 后自动生成正式 marker/QC 表；表格未完成前拒绝群体审阅。KEEP/DELETE 与最终命名分为两个停点；DELETE 后从 retained raw counts 重算下一轮，稳定轮完成后才锁定 Part 1。前端切换运行会重置临时状态，失败任务可重试。`tests/test_part1_review_workflow.py` 和锁定/链路回归覆盖状态转换；真实 Run #1 仍为 `CHOOSE_RESOLUTION`。

## 2026-10-12 Part 1 marker/QC 表格质量修复

状态：代码已更新，真实表格待重跑。Formal Engine 现在兼容真实合并对象的 QC 字段，并从 counts 补算缺失的核糖体比例、Top 50 基因比例和复杂度；新增逐行 marker 证据表，记录群内/群外检出率、检出率差和描述性质量等级。Studio API 与右侧界面拆分 QC 汇总和 Marker 证据两张表，旧紧凑 marker 文件保留兼容读取。Scrublet 未保存时明确显示“对象未保存”。TypeScript 与 AST 语法检查通过，完整 Python 回归受当前 Windows 环境 DLL/解释器问题影响尚未完成。真实 Run #1 未改变，人工审阅仍需用户完成。
