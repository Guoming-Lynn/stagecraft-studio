---
description: Stagecraft Studio 常驻约束
alwaysApply: true
---

# Stagecraft Studio 开发约束

完整任务书：skill 仓库 docs/CURSOR_PRODUCT_BUILD_PLAN.zh-CN.md。本文件优先级高于单轮指令。

## 产品红线
- 不接入 AI 也必须能完成 Part 1–5。任何功能不能依赖模型。
- 运行时不存在任意代码执行：无 shell=True、eval、exec、pickle.load、动态 import 外部字符串、自由 R/Python 文本。
- worker 只接受注册表里的 task ID 与 Pydantic 校验过的参数。
- 规则在后端执行。前端禁用按钮不算约束。
- 人工审阅（分辨率选择、KEEP/DELETE、命名、协议冻结）只能由用户经 API 提交，绑定 run_id + 证据 hash + cluster 集合 hash。
- AI 只能读授权摘要、创建 Proposal；不能改配置、冻结协议、提交审阅、改状态。
- 注释阶段目标基因数据在服务端过滤（盲审）。
- 不放宽科学限制：校准未完成、joint_common_slope 仅探索性、LODO 不是外部复制。
- 速览（quicklook）是细胞水平探索性分析：产物带 analysis_tier: quicklook，不能作为正式分析的输入，临时标签、自动分辨率和自动选中的细胞群不能被导入为正式审阅决策或默认值。看过速览的目标基因结果后，正式审阅记为 UNBLINDED_WITH_REASON。
- 运行时不向第三方服务发送用户数据：富集使用本地 GMT，不调用 Enrichr 等在线接口。

## 架构
- 两个引擎：正式分析在 target-gene-scrna-stagecraft（scripts/ 与 stagecraft/），速览在 scrna-target-pipeline。Studio 只以子进程调用，两个引擎之间不互相 import。
- Studio 是一个 Python 包 stagecraft_studio/ 加一个前端 web/。不新建其他顶层目录。
- 本地单用户：单 worker、SQLite、线性阶段失效。不做租约、心跳、幂等键、分布式、插件。

## 卫生
- 写新函数前先搜索是否已有实现。同一职责只有一处。
- 根目录不放 test.py、debug.py、scratch_*、tmp_*、*_old.*、*_v2.*、*_backup.*。不提交 .ipynb。
- 无注释掉的代码、无 print 调试、无无编号 TODO、无裸 except、无 except: pass。
- Python 文件 > 400 行、React 组件 > 300 行要拆分，或文件头写 `# hygiene: <原因>`。
- 无单实现抽象基类、单产品工厂、不变的配置项。
- 工具唯一：uv、ruff、mypy、pytest；pnpm、eslint、prettier、vitest、playwright。
- 依赖 pin 精确版本；新增依赖要说明为什么标准库或已有依赖做不到。
- docs/ 只有 architecture.md、capability-map.md、rule-coverage.md、milestones.md、install.md。不创建 SUMMARY/NOTES/PROGRESS/REPORT 类文档。
- 生成文件（TS 类型、rule-coverage.md）由脚本生成，CI 校验一致。
- 不提交数据、模型权重、.env、日志、输出目录；fixture 只用合成数据，总量 ≤ 5 MB。
- 提交小而单一，前缀 feat/fix/refactor/test/docs/chore；格式化改动单独提交。

## 完成标准
- 每个里程碑结束贴出：测试命令与实际输出、scripts/check_hygiene.py 输出、未使用代码清理结果、git status、未验证项。
- 「已完成」必须有可运行证据。页面数量、代码行数、自我评价不算。
- 研究设计决定、真实凭据或必要数据缺失时停下来问；普通工程选择自主推进。
- 测试可用明确标注的人工决策 fixture，不得伪装成真实用户审阅。
