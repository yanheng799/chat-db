## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

在 Issue 002 核心 SSE 查询流程之上，补齐对话页全部异常边界：确认卡片渲染（审核门）、查询重试、60 秒超时、空结果友好提示、SSE 中途断开处理、SQL 块复制按钮（已部分在 002 中完成）。

具体清单：
- `components/shared/ConfirmCard.tsx`：审核确认卡片组件。后端返回 `need_confirm` 事件时，替换系统气泡。当前降级为文本列表（后端 item 无 type 字段）：列出所有 item 的 reason/field，底部「确认」和「取消」按钮
- 确认/取消逻辑：「确认」→ POST `/api/query/{id}/confirm` { confirmed: true } → 更新气泡文案"已确认"（stub：后端当前返回 acknowledged，不恢复 pipeline）；「取消」→ POST `/api/query/{id}/cancel` → 更新气泡文案"查询已取消"
- `components/shared/ErrorCard.tsx`：错误卡片组件，红色边框 + 错误详情 + "🔄 重试"按钮。重试时复用 Issue 002 的 sendQuery 逻辑，用相同的 text 重新发起查询
- 超时处理：`useQuerySSE` hook 中 AbortController 60s 超时 → 显示 "⏱ 查询超时（超过 60 秒），请尝试缩小查询范围" + 重试按钮
- 空结果处理：SSE `result` 事件中 `rows` 为空数组时 → 显示绿色提示 "✅ 查询成功，但没有匹配的数据"（非红色错误），不显示空表格
- SSE 断开处理：`fetch-event-source` 的 `onerror` 回调 → 如果已收到部分内容（messages 非空）则显示 "⚠ 连接中断" 警告条；如果未收到任何内容则等同于网络错误（显示 ErrorCard + 重试）
- SQL 块复制按钮：`navigator.clipboard.writeText(sql)` + 复制后短暂显示"已复制"反馈

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 后端返回 `need_confirm` SSE 事件（items 含 reason 列表），When 渲染确认卡片，Then 显示待确认项列表 + 「确认」「取消」按钮
- [ ] Given 确认卡片显示，When 点击「确认」，Then 气泡更新为"已确认"；点击「取消」，Then 气泡更新为"查询已取消"
- [ ] Given 查询返回错误，When 显示错误卡片，Then 包含错误详情文字 + 红色边框 + "🔄 重试"按钮
- [ ] Given 错误卡片显示，When 点击「重试」，Then 使用原查询文本重新发送 POST /api/query → SSE 流重新开始
- [ ] Given 查询执行超过 60 秒，When AbortController 触发超时，Then 显示 "⏱ 查询超时（超过 60 秒）" + 重试按钮
- [ ] Given SQL 执行成功但返回 0 行（rows: []），Then 显示绿色 "✅ 查询成功，但没有匹配的数据"
- [ ] Given SSE 流中途断开且已有部分消息，Then 在最后一条消息后追加黄色警告 "⚠ 连接中断"
- [ ] Given SSE 流中途断开且无任何消息，Then 等同于网络错误，显示 ErrorCard + 重试

## Blocked by

- 002（chat-sse-query-bubbles）— 依赖 useQuerySSE hook 和 sendQuery action

## Notes

- 确认卡片降级：当前后端 need_confirm item 无 `type` 字段，统一按文本列表渲染，不做 time/enum/quantifier 类型区分
- 确认/取消降级：当前后端 confirm/cancel 端点返回 `acknowledged` 不实际恢复/中止 pipeline → 前端点击后仅更新 UI 文案
- 重试复用：ErrorCard 的 onRetry 回调直接调用 `useChatStore.sendQuery(lastQueryText)`
- 复制反馈：`navigator.clipboard.writeText()` 后按钮文字短暂变为 "✓ 已复制" 1.5 秒后恢复
