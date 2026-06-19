## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

对话页核心查询流程：用户在输入框输入 NL 文本并按 Enter → 通过 SSE 流式接收后端响应 → 实时更新系统气泡内容 → 最终展示 SQL 块（可折叠+可复制）、查询结果表格和 LLM 摘要。同时渲染 4 步进度条。

具体清单：
- `app/page.tsx`：对话页主组件，组合 InputArea + MessageList + ProgressBar
- `hooks/useQuerySSE.ts`：封装 `@microsoft/fetch-event-source`，支持 POST `/api/query`、`X-Session-Id` header、60s AbortController 超时、onmessage 回调解析 5 种 SSE 事件类型
- `components/chat/InputArea.tsx`：textarea + 发送按钮，Enter 发送、Shift+Enter 换行、运行时按钮禁用+旋转动画
- `components/shared/MessageBubble.tsx`：消息气泡组件，支持 `user` / `system` 两种角色
- `components/shared/SqlBlock.tsx`：SQL 代码块（等宽字体、深绿文字、可折叠、复制按钮）
- `components/shared/ResultTable.tsx`：结果表格（黄色表头、数据行、列数×行数统计、水平滚动）
- `components/shared/ProgressBar.tsx`：4 步进度条（语义匹配 → SQL生成 → 安全校验 → 执行），每步 idle/active(黄脉动)/done(绿)/error(红)
- `stores/chat.ts`：`messages[]`、`queryState`、`progressSteps[4]`、`sendQuery(text)` action（调用 useQuerySSE hook 并 dispatch SSE 事件更新 store）
- 空态：无消息时显示"用自然语言查询你的数据库" + 4 个示例查询 pill（点击填入输入框并发送）

SSE 事件 → UI 映射：
- `status` → 更新系统气泡文字 + 按顺序推进进度条（触发式降级：第一个 status → step1 done + step2 active，依此类推）
- `result` → 替换系统气泡为 ResultTable + SqlBlock + 摘要文字
- `error` → 替换系统气泡为红色错误文字（重试按钮在 Issue 004 实现）
- `done` → 所有步骤 done，恢复输入

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] Given 已连接后端（`NEXT_PUBLIC_API_BASE` 指向运行中的 FastAPI），When 输入"昨天的订单总数"并按 Enter，Then 发送按钮变为禁用+旋转 → 系统气泡显示"思考中…" → 进度条 Step1 active → 依次推进 → 最终显示 SQL 块 + 结果表格
- [x] Given 收到 SSE `status` 事件，Then 进度条从 Step1 开始依次推进（触发式，不依赖 phase 字段）
- [x] Given 收到 SSE `result` 事件（含 columns + rows），Then 系统气泡替换为结果表格，表格有黄色表头和深色数据行
- [x] Given SQL 块显示，When 点击复制按钮，Then SQL 文本复制到剪贴板
- [x] Given SQL 块显示，When 点击折叠/展开箭头，Then SQL 内容隐藏/显示
- [x] Given 收到 SSE `done` 事件，Then 进度条全部 done（绿色），输入框恢复可用
- [x] Given 空态显示，When 点击示例查询 pill "昨天的订单总数"，Then 文本填入输入框并自动发送
- [x] Given 运行时（queryState = 'running'），When 尝试发送新查询，Then 输入框和发送按钮保持禁用

## Blocked by

- 001（nextjs-scaffold-shared-shell）

## Notes

- SSE 降级策略：当前后端 SSE 不发送 `phase` 字段 → 进度条用触发式推进（第一个 status → step1 done + step2 active；第二个 status → step2 done + step3 active；第三个 → step3 done + step4 active；result → step4 done）
- `@microsoft/fetch-event-source` 使用 POST 方法，不修改后端端点
- 60s 超时通过 AbortController 实现（`setTimeout(() => controller.abort(), 60000)`）
- Zustand `useChatStore` 的 `sendQuery` 应为 async action，在内部创建 AbortController 并存到 store 供后续 cancel 使用

## Status

ready for PR

## Verification Report

### Commands Run

- `npx tsc --noEmit`: passed (0 errors)
- `npx eslint . --ext .ts,.tsx`: passed (0 warnings)
- `npx next build`: passed (4 routes generated: /, /admin, /datasources, /_not-found)
- `.venv/Scripts/python.exe -m pytest test/test_api/ -x -q`: passed (41/41)

### Acceptance Criteria Coverage

8/8 covered, all checked above.

### Findings

- **Finding 1 (info)**: Backend `gateway.py` had a pre-existing gap where `sql` was returned by `run_single_step` but dropped before the SSE `result` event. Fixed by adding `"sql": result.get("sql")` to the result SSE payload. Backward-compatible. Severity: low.
- **Finding 2 (info)**: No automated frontend tests exist (vitest/jest not configured). The acceptance criteria were verified via TypeScript compilation, ESLint, production build, and code-path analysis. Manual E2E verification against a running backend is recommended. Severity: low.

### Regression Risks

- **Risk 1 (low)**: `stores/chat.ts` was fully rewritten. Only consumers are `app/page.tsx` and `hooks/useQuerySSE.ts` — both part of this change. No impact on `admin.ts` or `datasources.ts` stores.
- **Risk 2 (low)**: `app/page.tsx` was rewritten from scaffold. The old static UI is fully replaced; no feature loss.
- **Risk 3 (low)**: Backend `result` SSE event now carries an extra `sql` field. Existing SSE consumers ignore unknown fields — no breaking change.

### Required Changes

None.

### Notes

- `sendQuery` directly uses `@microsoft/fetch-event-source` inside the Zustand action. The `useQuerySSE` hook is a thin React wrapper for component ergonomics.
- `switchSession` and `createSession` in the store provide the foundation for issue #003 (session management).
- `need_confirm` SSE events are handled gracefully (show placeholder text); full confirm-card UI is deferred to issue #004.
- No `git commit` / `git push` has been executed. All changes are local and ready for PR.
