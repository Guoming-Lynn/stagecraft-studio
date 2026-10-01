# 规则覆盖

由 `scripts/export_rule_coverage.py` 从 `stagecraft_studio/rules/catalog.py` 生成。
未落实的行只有说明，不能当成已经挡住了。

| 规则 | 类型 | 状态 | 位置 | 测试 | 说明 |
| --- | --- | --- | --- | --- | --- |
| PROTOCOL_HASH_MATCH | 机器校验 | 已落实 | stagecraft_studio/domain/protocol.py | test_changed_protocol_blocks_the_old_run | 冻结后的协议或输入变了，旧 stage run 不能继续。 |
| QUICKLOOK_NOT_FORMAL | 机器校验 | 已落实 | stagecraft_studio/rules/quicklook.py | test_quicklook_directory_is_rejected_before_launch | 正式入口拒绝带 quicklook 标记的目录。 |
| RESOLUTION_REVIEW_REQUIRED | 人工审阅 | 已落实 | stagecraft_studio/rules/gates.py | test_resolution_is_required_before_a_later_job | 分辨率选择要有 reviewer、日期、依据，并绑定 run 和证据 hash。没有有效选择不能入队。 |
| REVIEW_CLUSTER_COMPLETE | 人工审阅 | 已落实 | stagecraft_studio/rules/gates.py | test_old_cluster_review_does_not_apply_to_new_ids | 每个当前 Leiden id 恰好一行 KEEP 或 DELETE，不能有空白。旧审阅不能用于新聚类。 |
| REVIEW_BLINDING_RECORDED | 人工审阅 | 已落实 | stagecraft_studio/rules/gates.py | test_review_requires_a_blinding_value | 每次审阅记录 BLIND、UNBLINDED_WITH_REASON 或 NOT_APPLICABLE。 |
| BLINDING_EXPOSURE_RECORDED | 机器校验 | 已落实 | stagecraft_studio/rules/gates.py | test_quicklook_exposure_forces_unblinded | 同一项目看过速览目标基因结果时，审阅记为 UNBLINDED_WITH_REASON。 |
| DELETE_RECOMPUTE_REQUIRED | 机器校验 | 已落实 | stagecraft_studio/db/reviews.py | test_delete_cannot_reuse_the_old_umap | 有 DELETE 时从保留的 counts 重新跑网格，不沿用旧 UMAP。 |
| LINEAR_INVALIDATION | 机器校验 | 已落实 | stagecraft_studio/db/reviews.py | test_upstream_change_invalidates_downstream | 上游一变，下游 INVALIDATED，旧结果只读。 |
| INPUT_COUNTS_VALID | 机器校验 | 未落实 |  |  | counts 不合法时在预检阻断。正式引擎已拒绝非整数，Studio 入口还没接。 |
| TARGET_MEASURED_IN_COMMON_SET | 机器校验 | 未落实 | stagecraft_formal/merge.py |  | 目标基因不在 strict-common 就停止。规则在正式引擎，Studio 规则表还没接。 |
| DONOR_MAPPING_REQUIRED | 机器校验 | 未落实 |  |  | 缺失身份对应关系时阻断 donor 推断。 |
| DOUBLET_FAILURE_EXPLICIT | 机器校验 | 未落实 | stagecraft_formal/qc.py |  | Scrublet 失败不能当成全是 singlet。规则在正式引擎，Studio 规则表还没接。 |
| PER_LIBRARY_QC | 机器校验 | 未落实 | stagecraft_formal/qc.py |  | MAD 与 Scrublet 逐 library 估计。 |
| LINEAGE_ROUND_LIMIT | 机器校验 | 未落实 |  |  | 两轮后仍混杂则停止该 lineage。 |
| DESIGN_ESTIMABLE | 机器校验 | 未落实 |  |  | 按冻结模型检查秩和暴露变化。 |
| CLAIM_SCOPE_ALLOWED | 机器校验 | 已落实 | stagecraft_studio/rules/scientific_status.py | test_a_stored_pass_does_not_raise_the_ceiling | 描述性阶段不能获得 donor 推断资格。associated 只有来源块留一被记录后才可能为 true。 |
| CALIBRATION_STATUS_PRESERVED | 机器校验 | 已落实 | stagecraft_studio/rules/scientific_status.py | test_a_stored_pass_does_not_raise_the_ceiling | 校准状态不得因软件跑完或请求里写了通过而升级。 |
| QUICKLOOK_LABELS_PROVISIONAL | 机器校验 | 已落实 | stagecraft_studio/db/reviews.py | test_quicklook_carry_omits_labels_and_resolution | 从速览带入时只保留数据路径、字段映射和目标基因。 |
| LINEAGE_ROUND_LIMIT | 机器校验 | 已落实 | stagecraft_formal/part3.py | test_two_mixed_rounds_stop_the_lineage | 两轮后仍然混杂就停止这个 lineage。 |
| QUICKLOOK_CLAIM_SCOPE | 纯说明 | 未落实 | stagecraft_studio/api/copy.py |  | 主张范围只写在 CLAIM_SCOPE。结果页已显示，规则函数还没接。 |
