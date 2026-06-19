# STATUS

状态：issues-ready（6 个本地 AFK issue 草稿已生成，待实现或发布）

- 2026-06-19：`team-spec-refine` 5 轮，确认：
  - 范围 = 收编 3.4 热词词典（10–15 热词 + 2–3 公式 + 5–10 行业术语、无 CRUD UI）+ 5.1–5.5 全含。
  - 管道顺序 = 时间前置 → 语义匹配（四层递进）→ 枚举/区域/名称后置标准化 → SQL 生成 → 安全校验 → 审核阻断（统一用户确认）→ SQL 执行 → 结果总结。
  - 审核阻断 = LLM 兜底 + Phase 4 need_confirm 合并批量用户确认，用户确认后执行。
  - 热词规模 = 小规模精选（V1 不求全，主体靠向量检索/LLM 兜底）。
  - 安全/SQL 故障 = 安全失败告用户+LLM 重生成一次；SQL 超时/错误只报不愈（自愈延 Phase 7）。
- 延期项：错误自愈（Phase 7）、管理端审核 UI/策略配置/热词 CRUD UI（Phase 10）。
- 下一步：`team-spec-review` 复查 `spec/refine.md` 是否 ready；通过后 `team-spec-to-prd`。
