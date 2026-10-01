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

状态：已提交 `22a55a6`。根目录 `LICENSE` 是 `Copyright 2026 GuomingLin. All rights reserved.`。仓库仍是公开的，这一提交还没推送。

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

## M4 验收

| 条款 | 状态 |
| --- | --- |
| 人工 gate 跳不过去，直接调 API 也不行 | 通过 |
| 旧审阅不能用于新聚类 | 通过 |
| Scrublet 失败路径有测试 | 通过。测试在正式引擎 |
| 新引擎 CI 在 ubuntu 和 windows 通过 | 未满足。正式引擎没有远端 |
| 从速览开始只带入路径、字段映射和基因 | 通过 |
| 合成多 library 数据从 Part 1 走到 Part 3 一轮 | 未满足 |

## M5 验收

| 条款 | 状态 |
| --- | --- |
| 同一主线在 GUI 里跑通 | 未满足。后台 worker 已支持正式任务执行并通过真实引擎串联测试，完整 GUI 联动待验证 |
| skill 仓库已有科学回归不退化 | 无证据 |
| 不可估计和校准限制在界面和报告中保留 | 报告和审阅页有。图库页和阶段工作区没有 |

## 剩余工作

见 skill 仓库本机文件 `docs/STUDIO_AUDIT_FIXLIST.local.md` 的 P7 到 P13。P1 到 P6 是记录和生成文件校验，不改变分析行为。
