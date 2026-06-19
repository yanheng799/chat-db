# Chat-DB Next.js 前端重写 — 规格评审

- **评审对象**：`team-spec/active/2026-06-19-chat-db-nextjs-frontend/spec/refine.md`
- **评审日期**：2026-06-19
- **评审轮次**：第 2 轮（第 1 轮反馈 3 个 P1 已由 refine 第 9 轮解决）
- **评审范围**：技术选型、范围边界、异常处理、验收口径、风险扫尾

## 结论

**Status: ready**

第 1 轮评审发现的 2 个 P1 问题已在 refine 第 9 轮全部确认解决：激活数据源 ID 通过新增 `GET /api/admin/active-data-source` 端点获取（方案 B），`frontend/` 目录先 `git rm chat.html` 再 `create-next-app`（方案 A）。空态行为和 Tailwind 设计 Token 映射方向亦已补充。无剩余 P0/P1。规格清晰度足够进入 PRD 固化。

## 阻塞项

无。

## 风险清单（已更新）

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|------|------|---------|------|-----------|---------|-------|--------|
| P1 | 后端 SSE 不区分 phase | 进度条只收到 `starting` | 4 步进度条无法准确展示阶段 | `gateway.py:50` 仅发送 `"starting"` 无 `phase` 字段 | 前端降级为触发式进度条；后续后端增加 `phase` 字段后再联动 | 后端 | PRD 标注 |
| P1 | need_confirm item 无 `type` 字段 | 确认卡片无法按类型渲染不同控件 | 所有 item 统一显示文本列表 | gateway.py need_confirm items 无 type 字段 | 前端统一渲染文本列表；后续后端增加 `type` 后丰富交互 | 后端 | PRD 标注 |
| P1 | confirm/cancel 为 stub | 用户点击确认/取消 | pipeline 不恢复/不中止 | `gateway.py:116-122` 返回 acknowledged | 前端点击后仅更新 UI 文案 | 后端 | Phase 10+ |
| ~~P1~~ | ~~管理端图谱卡片无法获取 data_source_id~~ → **已决议**：新增 `GET /api/admin/active-data-source` 端点 | — | — | — | — | — | — |
| P2 | 审核策略进程内存存储 | 服务重启 | 策略回退默认值 | `admin.py:274` `_AUDIT_POLICY` 模块级 dict | 前端保存后 Toast "注意：服务重启后策略将恢复默认" | 前端 | 开发阶段 |
| P2 | SSE 流无超时控制 | 后端 pipeline 卡住 | 用户看永久"思考中…" | gateway.py 无 `asyncio.timeout` | 前端设 60s 整体超时（AbortController），超时显示"查询超时" | 前端 | 开发阶段 |
| P2 | shadcn/ui CSS 变量 vs 现有自定义变量 | 两套体系并存 | 视觉不一致 | chat.html 自定义 20+ CSS 变量 | 统一使用 shadcn 的 CSS 变量体系，在 tailwind.config.ts 中映射为当前暗色主题色值 | 前端 | 开发阶段 |
| P2 | 同步/学习触发后固定 2s 轮询 | 同步耗时 > 2s | 状态不准 | `chat.html:487` `setTimeout(loadSyncStatus, 2000)` | 改为每 2s 轮询直到 success/failed，最多 30 次 | 前端 | 开发阶段 |
| P3 | 无 Docker Compose 文件 | 生产部署 | 不影响前端独立开发 | `docker-compose*.yml` glob 返回空 | 记录为后续交付项 | DevOps | 上线前 |

## 需要补充的问题（均已处理）

1. ~~管理端空态设计~~ → refine.md 已补充 3 种空态行为
2. ~~数据源管理页的导航~~ → refine.md 已明确：`/datasources` 列表页，`/datasources/[id]` 详情页为全屏替换（非抽屉）
3. ~~Tailwind CSS 变量体系~~ → refine.md 已确认：统一使用 shadcn/ui 的 CSS 变量体系

## Questions For User

（第 1 轮 3 个问题已由用户选择 B, A, A，均已写入 refine.md 第 9 轮变更）

## Required Refinement

（所有第 1 轮要求的 refine 修改已在第 9 轮完成）
