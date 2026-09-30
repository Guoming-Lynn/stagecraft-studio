# 能力盘点

状态：M0-B 只读盘点，2026-09-30。没有改 skill 仓库的已跟踪文件，也没有改 `D:\scrna-target-pipeline` 里的已有文件。重跑输出在 `D:\tmp\stagecraft-m0b-rerun\GSE167363`。

实现方式只使用三个词：复用、新增、后置。没跑过的计算标「未验证」。没有执行代码的标「待实现」。

## 依赖是否冲突

速览目录 `D:\scrna-target-pipeline\00_skill\scrna-target-pipeline` 没有 `pyproject.toml`、`requirements.txt` 或版本 pin。因此不能做「两份 pin 对 pin」的比较。能核对的是 stagecraft 已声明的范围，和本机唯一能同时导入两边科学包的环境 `D:\miniforge\envs\sc_analysis`。

| 包 | stagecraft 声明 | sc_analysis 3.11.15 实测 | 结论 |
| --- | --- | --- | --- |
| Python | `>=3.10,<3.12` | 3.11.15 | 落在范围内 |
| numpy | `>=1.24,<3` | 2.4.6 | 落在范围内 |
| pandas | `>=2.0,<3` | 2.3.3 | 落在范围内 |
| scipy | `>=1.10,<2` | 1.17.1 | 落在范围内 |
| anndata | `>=0.9,<0.13` | 0.12.19 | 落在范围内，靠近上界 |
| scanpy | `>=1.9,<1.12` | 1.11.5 | 落在范围内 |
| matplotlib | `>=3.7,<4` | 3.11.1 | 落在范围内 |
| seaborn | `>=0.12,<1` | 0.13.2 | 落在范围内 |
| harmonypy | `>=0.0.10,<1` | 0.2.0 | 落在范围内 |
| leidenalg | `>=0.9,<1` | 0.12.0 | 落在范围内 |
| scrublet | `>=0.2,<1` | 0.2.3 | 落在范围内 |
| igraph | `>=0.10,<1` | 1.0.0 | 冲突：安装版不满足 `<1` |
| gseapy | 正式分析未声明 | 1.1.13 | 只被速览使用 |

命令：

```text
D:\miniforge\envs\sc_analysis\python.exe -c "import importlib.metadata as m; print({n: m.version(n) for n in ['scrublet','scanpy','anndata','igraph','leidenalg','harmonypy','gseapy']})"
```

输出摘要：`igraph 1.0.0`，其余见上表。

同一个环境跑正式分析测试时崩溃，不是只差一个版本号：

```text
D:\miniforge\envs\sc_analysis\python.exe -m pytest -p no:cacheprovider -q tests/test_stage_handoffs.py
```

输出摘要：跑到 `part4_identifiability._spearman` 时 Windows fatal exception `0xc06d007f`，栈在 numpy `cov` / scipy `spearmanr`。退出码不是 0。

同一组测试在 Python 3.10.8（numpy 1.25.0，scipy 1.15.3）上通过，见下文「Part 4」。结论：现在不能把两个引擎放进这一个 `sc_analysis` 环境就当作兼容。冲突留在引擎仓库解决，本切片不改依赖。

Python 3.10.8 本机 site-packages 能过 `check_environment.py --stage smoke` 和 `--stage part5`，但 `--stage part1` 失败，因为没有 scanpy、scrublet、harmonypy、igraph、leidenalg。

## 速览重跑

数据集：策展结果里最小的、输入文件仍然存在的 `GSE167363_IFITM3_Sepsis`。输入 `D:\scrna-target-pipeline\05_new_test_plan\inputs\GSE167363_IFITM3.h5ad`，64244 细胞 × 33538 基因，1.37 GB。`GSE149689` 和 `GSE161267` 的策展目录没有 `config.json` 和 h5ad，这次不能重跑。

命令（输出只写到临时目录，`QUICK_MODE` 为 true）：

```text
D:\miniforge\envs\sc_analysis\python.exe D:\scrna-target-pipeline\00_skill\scrna-target-pipeline\scripts\run_pipeline.py --config D:\tmp\stagecraft-m0b-rerun\GSE167363\config.json
```

输出摘要：退出码 0，墙钟约 12 分钟（08:18:50–08:30:54）。四阶段返回码都是 0。phase02 / phase03 状态是 `quick_provisional`。QC 后 39864 细胞。自动分辨率 `Selected_Resolution=0.4`，`N_Clusters=10`。`analysis_unit=cell`，`donor_level_inference=false`。富集报告写明 `backend=gseapy.enrichr/prerank`，`status=completed`（ORA up FDR 行 533）。这是在线 Enrichr 路径，不是本地 GMT。

图数量和质量结论与策展副本不一致：

| 项 | 本次重跑 | 策展副本里保存的质量报告 |
| --- | --- | --- |
| 质量状态 | `reject`，原因 `low_information_figure_present`，审计 25 张，6 张不合格 | `pass`，审计 25 张，0 张不合格 |
| PNG | 46 | 47 |
| 少掉的 PNG | `04_deg/volcano_HC_Control_IFITM3_high_vs_low.png` | 策展副本有这张 |
| 汇总图 | 没有 `06_portfolio`（质量拒绝后跳过） | 有 `06_portfolio` |

顶层 `pipeline_status.json` 的 `outcome` 仍是 `completed_analysis`，同时 `figure_quality.status` 是 `rejected_dataset`。拒绝没有升到总结果。这是缺口，不是本次要改的代码。

## 正式分析引擎

### 环境门

- 规范要求：运行前知道 Python 与 R 包是否在。门通过不等于科学有效。
- 现有入口：`scripts/check_environment.py`。
- 真实输入输出：`--stage` 选择 smoke / part1–part6，stdout 是 JSON。
- 测试覆盖：本次直接运行。仓库测试未把这次 JSON 当夹具。
- 缺口：只检查能否导入，不检查 pin。igraph 1.0.0 仍显示 PASS。
- 实现方式：复用。
- 命令：`python scripts/check_environment.py --stage part5`（Python 3.10.8）。输出摘要：`status=PASS`，含 R 包 limma 3.66.0、edgeR 4.8.2、fgsea 1.36.2、Matrix 1.7.5。
- 命令：`python scripts/check_environment.py --stage part6`。输出摘要：`status=FAILED`，torch 2.0.1 与 transformers 4.30.2 能导入，`geneformer` 模块不存在，并写明模型文件门未过。

### Part 1 目录骨架

- 规范要求：逐 library QC、Scrublet、Harmony、Leiden，然后人工锁定。
- 现有入口：`scripts/part1_init.py`。
- 真实输入输出：`--out` 与 `--gene`。写出 `00_protocol_manifest` 到 `06_reports` 和一份 `PROTOCOL.md`。
- 测试覆盖：本次运行。没有 QC 数值测试，因为没有 QC 执行器。
- 缺口：帮助文本写明不做 QC、Harmony、Leiden。`part1_qc.py`、`part1_load.py`、`part1_merge.py`、`part1_resolution_grid.py` 均不存在。待实现。
- 实现方式：骨架复用；执行器新增。后置到 M4。
- 命令：`python scripts/part1_init.py --out %TEMP%\stagecraft-m0b-part1 --gene IFITM3`。输出摘要：退出码 0，`No Scanpy runner is bundled.`

### Part 2 目标基因图

- 规范要求：在已锁定对象上做检测率与表达展示。图脚本不是聚类分析器。
- 现有入口：`scripts/part2_figures.py`。文档写明只读，检测定义为 raw count > 0，强度用 `layers['normalized']`。
- 真实输入输出：h5ad、基因、分组、颜色表，输出图目录。
- 测试覆盖：未验证。本次没有一份带 UMAP 和 normalized layer 的锁定 h5ad，没有跑这个脚本。
- 缺口：没有独立的 Part 2 统计执行器。
- 实现方式：绘图入口复用。新的统计执行器只有在盘点后仍缺计算时才新增；当前未见除作图以外的 Part 2 计算入口。

### Part 3 删除与轮次

- 规范要求：DELETE 之后从保留的 counts 重算 HVG 和 Leiden，不沿用旧 UMAP。两轮后仍混杂则停止该 lineage。
- 现有入口：`part3_prepare_removal.py`、`part3_decision_template.py`、`part3_round_audit.py`、`part3_figures.py`。
- 真实输入输出：removal 读父级 raw 与决策表，写出被删对象和子级 raw。它的文档写明不重算 HVG、PCA、Harmony、邻居、UMAP 或 Leiden。
- 测试覆盖：`tests.test_stage_handoffs` 在 Python 3.10 上通过，并打印 `Run run-leiden on the child; no old embedding is reused.`
- 缺口：`part3_recluster.py` 不存在。待实现。测试证明的是「留下 raw、不复用旧嵌入」，不是「已经重聚类」。
- 实现方式：removal / audit / figures 复用；recluster 新增。后置到 M4。

### Part 4 可识别性预检

- 规范要求：在 donor 单元上判断以后的斜率能不能估计。不拟合 limma，不重开标签。
- 现有入口：`scripts/part4_identifiability.py`。`part4_figures.py` 是另一份作图脚本，本次未跑，标未验证。
- 真实输入输出：单位表 CSV 进，`identifiability.csv` 加 PNG/PDF/SVG 出。
- 测试覆盖：上面的 3.11 崩溃发生在这条 spearman。3.10 的 CLI 成功。
- 缺口：结果是预测旗标，不是拟合判决。
- 实现方式：复用。
- 命令：`python scripts/part4_identifiability.py units.csv --group subtype --out part4`（3 行合成表，`MPLBACKEND=Agg`）。输出摘要：退出码 0，3 行旗标都是 `LOW_N`，`source_independence=NOT_ESTABLISHED_BY_FORECAST`。

### Part 5 donor 推断

- 规范要求：目标基因排除在结局之外的 pseudobulk，再做 donor 水平模型。`joint_common_slope` 只能是探索性。`FROZEN_PASS` 不是校准证书。
- 现有入口：`part5_pseudobulk.py`、`part5_eligibility.py`、`part5_source_blocks.py`、`part5_cell_exploratory.py`、`part5_verdict.py`、`part5_figures.py`，以及 R 脚本 `part5_run_models.R`、`part5_run_pathways.R`、`part5_model_audit.R`、`calibrate_part5_null.R`。配置字段见 `scripts/part5_analysis_config.example.yaml`（估计对象、暴露、设计、资格阈值、通路参数）。
- 真实输入输出：pseudobulk 读锁定 h5ad，写出 `counts.mtx`、`genes.csv`、`metadata.csv`、`pseudobulk_audit.json`。R 模型脚本本次未跑，标未验证。
- 测试覆盖：`python -m unittest tests.test_stage_handoffs tests.test_gates tests.test_review_boundaries`（Python 3.10.8，`PYTHONPATH` 含仓库根和 `scripts/`）31 项 OK，约 3.4 秒。其中包含资格、来源块和判决边界。全量 `pytest tests` 未跑，标未验证。`calibrate_part5_null.R` 的 1000 次 null 未跑，标未验证。
- 缺口：校准未完成。不要把本次工程命令写成科学认证。
- 实现方式：现有脚本复用。Studio 阶段工作区后置到 M5。
- 命令：`python scripts/generate_toy_data.py --out toy.h5ad`，接着 `python scripts/part5_pseudobulk.py toy.h5ad --gene TARGET_FEATURE --group cell_type --out pseudobulk`。输出摘要：640 细胞、8 donor、2 dataset；49 个基因 × 32 个单元；`genes.csv` 不含 `TARGET_FEATURE`；文本写明目标基因是暴露侧车，不是结局基因。

### Part 6 虚拟扰动

- 规范要求：specified / not turnkey，依赖获授权的 Geneformer 环境。
- 现有入口：`part6_eligibility.py`、`part6_endpoints.py`、`part6_controls.py`、`part6_axes.py`、`part6_smoke_gate.py`、`part6_sign_tests.py`、`part6_verdict.py`、`part6_figures.py`、`part6_token_audit.py`。
- 真实输入输出：本次只跑了环境门，没有跑推断。
- 测试覆盖：环境门失败，见上文。脚本级计算未验证。
- 缺口：无 `geneformer` 模块，无模型文件门。待实现的是「可安装的授权运行时」，不是再写一套未授权推断。
- 实现方式：后置。不进入首版主线。

### 主张检查与可复用库

- 规范要求：导出前能标出越界用语。hash、IO、claims 给 Studio 导入，不通过读 Markdown 决定通过。
- 现有入口：`scripts/claim_lint.py`，包 `stagecraft/hashing.py`、`io.py`、`claims.py`、`numeric.py`、`patterns.py`。
- 真实输入输出：lint 读 Markdown，打印 finding 数。
- 测试覆盖：`tests/test_review_boundaries.py` 含在上述 31 项里。`hash_inputs.py` 本次未跑，标未验证。
- 缺口：lint 通过不等于科学正确。
- 实现方式：复用。
- 命令：`python scripts/claim_lint.py %TEMP%\stagecraft-m0b-claim.md --target IFITM3`。输出摘要：`claim-lint: 0 finding(s) in 1 file(s). Review flags only.`

### Seurat 转换

- 规范要求：固定 R 任务 `convert_seurat_rds`，只取指定 assay 的 counts，并记录 Seurat 版本。
- 现有入口：无。`scripts/` 中没有 `convert_seurat`。
- 真实输入输出：无。
- 测试覆盖：无。
- 缺口：待实现。
- 实现方式：新增。后置到 M2 注册任务之前，执行代码放在 skill 仓库。

## 速览引擎

目录只有 `scripts/`、`references/`、`examples/`、`SKILL.md`。没有测试、LICENSE、依赖声明。`references/hadha_source/` 有 10 个文件，合计 424363 字节。

### 四阶段运行器

- 规范要求：QC/Scrublet、全局聚类、目标亚群、target high/low DEG 与富集。细胞水平，不做 donor 推断。
- 现有入口：`scripts/run_pipeline.py`。阶段表是 phase01、phase02、phase03、`phase05_sensitivity_deg.py`。`phase04_pseudotime.py` 不在这个表里。
- 真实输入输出：`--config` JSON。写出 h5ad、表、图、`99_logs/pipeline_status.json`。
- 测试覆盖：无测试目录。本次有一次真实重跑，见上文。
- 缺口：质量拒绝不改变顶层 `outcome`。`phase04_pseudotime.py` 留在主目录但未接入。
- 实现方式：运行器复用。隔离规则和「拒绝就不能写成 completed_analysis」新增，后置到 M1/M2。

### 自动分辨率与 QUICK_MODE

- 规范要求：自动选择要在结果里写明是启发式。临时标签不能进入正式审阅。
- 现有入口：`phase02_global_clustering.py` 取第一个产生 10–15 个 cluster 的分辨率。`human_review.py` 在 `QUICK_MODE` 下给出 `quick_provisional`。
- 真实输入输出：本次 `Selected_Resolution=0.4`，10 个 cluster，phase 状态 `quick_provisional`。
- 测试覆盖：无单测。本次重跑覆盖了这条路径。
- 缺口：报告 JSON 有选定值，没有面向用户的固定句子「分辨率由启发式自动选择」。待实现的是这句标注，不是再写一个选择器。
- 实现方式：选择逻辑复用；标注新增。后置到 M1。

### 图质量与汇总图

- 规范要求：空 violin、单类别 violin、常数图、无阳性 feature、无显著基因火山图要明确拒绝。
- 现有入口：`figure_quality.py`、`portfolio_board.py`。由 `run_pipeline.py` 在末尾调用。
- 真实输入输出：本次质量报告 `status=reject`，6 张具体到文件和原因。汇总图被跳过。
- 测试覆盖：无「每个拒绝原因一个用例」。待实现。
- 缺口：同一次数据的旧报告是 pass。重跑不可重复，M1 验收不能把旧 PNG 数当成已经对齐。
- 实现方式：检查器复用；测试新增。

### 在线富集

- 规范要求：产品运行时不得把基因列表发给 Enrichr。用本地 GMT。
- 现有入口：`phase05_sensitivity_deg.py` 调用 `gseapy.enrichr` 和 `prerank`。
- 真实输入输出：本次 `enrichment.backend=gseapy.enrichr/prerank`，`status=completed`。
- 测试覆盖：无离线测试。
- 缺口：待实现本地 GMT 路径。在改掉之前，速览不能进产品运行时。
- 实现方式：新增。后置到 M1。不要在 Studio 里临时包一层在线调用。

### 输入格式

- 规范要求：与正式分析白名单对齐。Seurat `.rds` 先走共用转换，不由速览自己读。
- 现有入口：本次配置是 `INPUT_FORMAT=h5ad`。脚本导入面没有 Seurat。
- 真实输入输出：h5ad 重跑成功。MTX、10x h5、csv/tsv 本次未跑，标未验证。`.rds` 无转换器，待实现。
- 测试覆盖：无。
- 实现方式：h5ad 复用。格式对齐与 Seurat 转换新增。

## 后置，不要在下一轮提前做

- M0-C：维护者确认规模之前，不写 `RESOURCE_LIMIT`。
- M1：速览去代理指令、离线 GMT、测试、pin、LICENSE、输入对齐。先处理 igraph 与 Python 3.11 崩溃，再把两个引擎放进同一个环境。
- M2 及以后：任务注册表、规则、API、GUI。本文件没有这些代码。
