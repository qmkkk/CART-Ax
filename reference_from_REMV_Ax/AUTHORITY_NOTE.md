# AUTHORITY NOTE — reference_from_REMV_Ax 目录组成（PRE_FORMAL_FINAL_FIX 更新）

- **唯一权威前作事实来源**：`final_clean_v2/C7_clean_release_bundle_20261004_v2/`
  （= C7_clean_release_bundle_20261004_v2.zip 解压内容，官方 sha256sums 81/81 校验一致）。
- 顶层 5 个文档（CLAIMS_AND_SCOPE.md、HANDOFF.md、final_results_audit.md、
  formal_experiment_report.md、README.md）已于 PRE_FORMAL_FINAL_FIX 替换为 v2
  权威版本（SHA256 与 final_clean_v2 内文件逐字节一致）。
- 旧 v1 版本中的 "ER ordering invariant / no shift anywhere" 等结论已被 v2
  推翻（v2：strict ER inversions 出现在 12/32/64 位 D2 等），v1 内容不再存在于
  本目录；历史失效记录见 reports/2.md。
- `run_report_5/6/7.md` 为历史开发记录（REMV-Ax C7 开发史），**不具权威性**；
  权威报告为 evidence/formal_experiment_report.md（v2）。
- `ENVIRONMENT.md`、`REPRODUCTION.md`、`pre_freeze_validation_report.md`、
  `commands_used.txt`、`tool_versions.txt`、`git_commits.txt`、`provenance_map.csv`
  与 v2 包逐字节一致（v1/v2 未变）。
- 冲突规则（AGENTS.md §2.0）：与 final_clean_v2 冲突时以 final_clean_v2 为准。
