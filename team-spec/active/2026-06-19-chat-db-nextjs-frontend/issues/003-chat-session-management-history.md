## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

对话页的会话管理功能：用户可创建多个会话、在侧边栏查看会话列表、切换会话并加载历史消息、首次查询无 sessionId 时自动创建会话。

具体清单：
- `stores/chat.ts` 扩展：`sessionId`、`conversations[]`（{id, title, time}）、`createSession()`、`switchSession(id)`、`loadHistory(sid)` actions
- `components/chat/ConversationList.tsx`：侧边栏会话列表渲染（当前激活会话黄色高亮、标题为首条查询截断前 24 字 + 时间）
- `app/layout.tsx` 或侧边栏组件集成 ConversationList
- 首次查询逻辑：`sendQuery` 中检查 `sessionId`，如为空则先 `POST /api/session` → 拿到 `session_id` → 存入 store → 再发查询
- 会话切换逻辑：点击会话项 → `GET /api/conversations/{session_id}` → 获取 `turns[]` → 解析 turns 为 messages → 渲染到消息区
- 会话标题自动更新：首条查询后，取查询文本前 24 字作为标题（`updateConversationTitle`）
- 新建会话按钮：侧边栏顶部 [+ 新建会话] → `POST /api/session` → 新会话添加到列表首位 → 清空消息区显示空态

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 无 sessionId，When 发送第一条查询，Then 自动调 POST /api/session → 获取 sessionId → 查询正常发送 → 侧边栏出现新会话项（标题为首条查询前 24 字）
- [ ] Given 侧边栏有多个会话，When 点击非当前会话，Then 调 GET /api/conversations/{sid} → 获取 turns → 将 user/assistant 交替渲染为消息气泡
- [ ] Given 当前会话有消息，When 点击「新建会话」按钮，Then 创建新会话 → 侧边栏新项出现 → 主区域显示空态
- [ ] Given 切换会话后，When 在新会话中发送查询，Then 查询使用新会话的 sessionId，原会话不受影响
- [ ] Given 会话创建时间，Then 在会话列表中显示格式化的时间（如"14:32"）

## Blocked by

- 001（nextjs-scaffold-shared-shell）

## Notes

- 会话切换时历史 turns 格式：`GET /api/conversations/{sid}` 返回 `{ session_id, turns: [{user, assistant}, ...] }`，user 为查询文本，assistant 为摘要文字。前端应按顺序渲染为交替气泡
- 会话列表本地也存一份（Zustand store），切换时直接从 store 取标题和时间，历史消息从 API 获取
- 可并行 Issue 002 开发——共享 `useChatStore` 但功能独立
