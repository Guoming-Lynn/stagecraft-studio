# 里程碑

任务书第 15 节是里程碑定义。这里只记录切片状态。

## M0-A 仓库骨架

状态：本机检查通过，尚未提交，GitHub CI 未跑。证据在 skill 仓库本地交接文件，不在本仓库重复贴日志。

## M0-B 只读盘点

状态：本机盘点已写入 `capability-map.md`。规模建议在 `architecture.md`，仍是待确认。GitHub CI 仍未跑。

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

状态：本机已改。表单不能指定要执行的程序。失败运行仍带 quicklook 标记。输入格式写入 `INPUT_FORMAT`。`quicklook_inspect` 列出 h5ad 的 obs 列。非空输出目录会拒绝。引擎 `BATCH_COLUMN` 默认值只在 `config_contract.py`。GitHub CI 仍未跑。

## 单元 B 后台运行与结果状态

状态：本机已改。`POST /quicklook` 立即跳到 `/runs/<id>`。同一时间只能有一次速览。取消会停掉进程树。结果页分开显示引擎、输入和图质量。`templates.py` 没有改。GitHub CI 仍未跑。

## 单元 D 引擎卫生检查和 CI

状态：在 `D:\scrna-target-engine`。本仓库没有改。

## 单元 E1 React 界面

状态：本机已改。`/api` 提供运行、步骤、文件、表格和脚本源码。页面是三栏。日志、代码、参数和图片在 React 里。`templates.py` 已删除。GitHub CI 仍未跑。

## 单元 E2 预览、表格、环境和演示

状态：已提交 `7d8a06b`。文件树点开后在中栏预览。CSV 搜索和排序走分页接口。环境页由后端给出通过或不通过。演示数据由引擎脚本现写，不提交 h5ad。GitHub CI 仍未跑。

`6746531` 拦住了表格向总行数之外要数据。3 行的 `genes.csv` 不再反复请求 `offset=3`。

## 界面返修

状态：已提交。字号只留 12/14/16/20/24 px，圆角只留 8 和 12，阴影两级，一个强调色。面板文案在 `web/src/text/chrome.ts`。产物质量用服务端 `quality_status`。助手只写「未接入」。`prettier --check` 通过。GitHub CI 仍未跑。

## 单元 E3 方法、复现包、对比和通知

状态：本机已改。方法段落由服务端模板生成，写明细胞水平、探索性、临时标签。复现包是 zip，含 config、argv、引擎信息，不含数据。两次运行并排对比参数、细胞数、cluster 数和图质量。运行从进行中变成结束时，已授权的浏览器可以发桌面通知。GitHub CI 仍未跑。

## 单元 F1 Host 头

状态：本机已改。`TrustedHostMiddleware` 只允许 `127.0.0.1` 和 `localhost`。`Host: evil.example` 请求 `/api/bootstrap` 得到 400，响应里没有令牌。GitHub CI 仍未跑。

## 单元 F2 合成矩阵四阶段

状态：在速览引擎 `d5f27cd`。Studio 没有改运行逻辑。80 细胞、250 基因的合成矩阵在断网时跑完四个阶段。图质量是拒绝。GitHub CI 仍未跑。

## 单元 F3 默认基因集

状态：留空时下载人和鼠的 Hallmark 与 GO Biological Process（MSigDB 2026.1）。KEGG 不下载，由用户导入 GMT。自己填的 GMT 优先。基因列表不外发。测试不联网。GitHub CI 仍未跑。

## 单元 F4 10x h5

状态：`.h5` 记为 `h5`，引擎用 `scanpy.read_10x_h5`。测试用合成矩阵。GitHub CI 仍未跑。

## 单元 F5 汇总图

状态：`06_portfolio` 的清单提供每一格的位置。页面点格打开原图，同名表在中栏打开。GitHub CI 仍未跑。

## 单元 F6 启动脚本

状态：`scripts/start-studio.cmd` 只调用 uv 和 pnpm。`@echo off` 之后执行 `chcp 65001`，中文提示按 UTF-8 显示。环境页每一项不通过都带修复说明。GitHub CI 仍未跑。

## M1 到 M7

状态：未开始。单元 F 还在做。正式分析和助手没开始。
