# 规格评审 — 上下文记忆与用户特征（Phase 8）

- **slug**：`2026-06-19-context-memory-profile`
- **评审日期**：2026-06-19
- **评审对象**：`spec/refine.md`（4 轮细化完成版）
- **评审依据**：设计文档 §十一、dev plan Phase 8、Redis 已启动
- **Status**：`ready`（无 P0、P1 为 Redis 单点依赖——可跟踪）

## 结论

4 轮细化覆盖全 5 子领域，验收可观察。无 P0、无阻塞 P1。最大风险来自「基础设施依赖」——Redis 是会话+缓存+特征暂存的唯一依赖，挂掉时记忆层降级。

## 阻塞项

无。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|
| P1 | Redis 单点依赖 | Redis 不可用 | 会话记忆/缓存/特征暂存静默降级 | 实现期加 Redis 连接健康检查 + 降级日志 | 实现者 | 开发时 |
| P2 | session_id → user_id 迁移 | Phase 9 认证上线 | 画像表/摘要表关联字段需变更 | V1 用 session_id，Phase 9 加 user_id 列+回填 | @yanheng | Phase 9 |
| P2 | 10 轮全量上下文超出 token 窗口 | 长对话 | LLM 调用失败或截断 | 每轮限制 500 tokens，超出截尾 | 实现者 | 开发时 |

## Change Log

- 2026-06-19：首次评审。4 轮细化完整、Redis 已启动。无 P0；P1 仅 Redis 依赖；2 项 P2。结论 `ready`。
