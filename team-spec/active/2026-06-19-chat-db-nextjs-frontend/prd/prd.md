# Chat-DB Next.js 前端重写

## 问题陈述

Chat-DB 当前前端为单文件 HTML 原型（`frontend/chat.html`，566 行），存在三方面不足：

1. **功能不完整**：数据源管理页面完全缺失，管理员只能通过 curl / Swagger 管理数据源连接
2. **交互缺陷**：进度条无法区分流水线阶段、确认卡片无类型化控件、会话切换不加载历史消息、图谱端点调用错误格式必然 422
3. **可维护性差**：单文件无模块化，所有逻辑耦合在全局作用域，难以扩展和团队协作

后端 API 体系已完备（Gateway + Admin + Datasources 三组路由），需要一个正式的 Next.js 前端将全部能力暴露给查询用户和管理员。

## 目标

- 用 Next.js 14+ App Router 重写全部前端，覆盖 3 页面：对话页 / 管理控制台 / 数据源管理
- 功能增强：补齐原型 8 项交互缺陷（见功能需求），达到产品可用标准
- 替换上线：完成后删除 `chat.html`，Next.js 版本成为唯一前端

## 非目标

- D3.js 知识图谱力导向图可视化（V2，本期用 tag 展示）
- 多步查询进度展示（依赖后端 `agents/graph.py` 实际执行，当前为 dry-run）
- 审核断点续传（依赖后端 confirm/cancel 实际恢复/中止 pipeline，当前返回 acknowledged）
- 认证系统（V1 内网部署，无认证）
- CSV/Excel 导出
- 移动端深度适配（响应式保证可用但不做移动端优化）
- 交互式图谱编辑（L3 人工补充，V2）

## 用户与场景

1. 作为**查询用户**，我打开 Chat-DB，输入"昨天的订单总数"，系统通过 SSE 流式返回 SQL、执行结果和摘要，进度条展示当前所在阶段。
2. 作为**查询用户**，当系统不确定我的意图（模糊时间、枚举别名、名称简称），我收到确认卡片，可查看备选值并确认或取消。
3. 作为**查询用户**，我可以创建多个会话、在会话之间切换，切换后能看到历史对话消息。
4. 作为**管理员**，我打开管理控制台，查看同步状态、知识图谱概况、管理值映射/热词/固定日期周期、配置审核策略。
5. 作为**管理员**，我打开数据源管理，新建数据库连接、测试连接、激活数据源、查看元数据概览、触发同步/学习、查看日志。

## 当前状态

- **后端**：3 组 FastAPI 路由（Gateway `/api`、Admin `/api/admin`、Datasources `/api/datasources`）已实现
- **前端原型**：`frontend/chat.html` 实现了对话页（SSE 流式、气泡、进度条、确认卡片、结果表格）和管理控制台（6 张卡片 toggle 显示），但有多处已知缺陷
- **缺口**：数据源管理页面前端完全不存在；管理端图谱卡片调用的端点路径格式错误（`/graph/nodes/active` 在 `{data_source_id}` UUID 路径参数下必然 422）；确认卡片无类型化交互；进度条无法区分阶段

## 方案描述

### 架构

```
frontend/                          ← Next.js 14+ App Router 项目
├── app/
│   ├── layout.tsx                 ← 共享 Shell：侧边栏 + 主区域
│   ├── page.tsx                   ← 对话页（首页 /）
│   ├── admin/
│   │   └── page.tsx               ← 管理控制台（/admin）
│   └── datasources/
│       ├── page.tsx               ← 数据源列表（/datasources）
│       └── [id]/
│           └── page.tsx           ← 数据源详情（/datasources/[id]）
├── components/
│   └── shared/                    ← 跨页面复用组件
│       ├── SqlBlock.tsx
│       ├── ResultTable.tsx
│       ├── ConfirmCard.tsx
│       ├── ErrorCard.tsx
│       ├── ProgressBar.tsx
│       ├── Toast.tsx
│       └── ConfirmDialog.tsx
├── stores/                        ← Zustand stores
│   ├── chat.ts
│   ├── admin.ts
│   └── datasources.ts
└── lib/
    ├── api.ts                     ← fetch 封装 + API_BASE
    └── sse.ts                     ← useQuerySSE hook
```

### 数据获取

- 所有页面浏览器直连 FastAPI（`NEXT_PUBLIC_API_BASE` 环境变量），不做 BFF 代理
- 对话页 SSE：`@microsoft/fetch-event-source` + 自定义 `useQuerySSE` hook，支持 POST + 自动重连
- 状态管理：Zustand（`useChatStore` / `useAdminStore` / `useDataSourceStore`）

### 技术栈

| 层 | 选择 |
|----|------|
| 框架 | Next.js 14+ App Router |
| 组件库 | shadcn/ui（Radix + Tailwind CSS） |
| 状态管理 | Zustand |
| SSE | `@microsoft/fetch-event-source` |
| 包管理 | pnpm |
| 代码检查 | ESLint（eslint-config-next） |
| 设计 Token | 统一使用 shadcn/ui CSS 变量体系，映射为当前暗色主题色值 |

### 对话页交互流程

```
用户输入查询
  → POST /api/query {text} + X-Session-Id
  → SSE 流式返回:
      status(阶段推进) → 更新进度条+系统气泡
      need_confirm(审核门) → 替换为确认卡片
      result(查询结果) → 替换为结果表格+SQL块+摘要
      error(错误) → 替换为错误卡片（含重试）
      done(结束) → 恢复输入
```

### 进度条阶段

```
语义匹配 → SQL生成 → 安全校验 → 执行

状态: idle(灰) / active(黄脉动) / done(绿) / error(红)
```

注意：后端 SSE 当前不发送 `phase` 字段 → 前端降级为触发式进度条（收到第一个 status 事件后依次推进），后续后端增加 `phase` 字段后再联动。

### 确认卡片按类型渲染

注意：后端 need_confirm item 当前无 `type` 字段 → 前端降级为统一文本列表。后续后端增加 `type` 后按类型渲染：
- `time_normalized` → 展示时间范围
- `enum_matched` → 展示备选值可点击切换
- `quantifier_fuzzy` → 提供输入框

### 管理端数据流

管理员操作 → 前端调用对应 Admin/Datasources API → 更新 Zustand store → 重新渲染卡片/列表。

关键依赖：管理端图谱/值映射卡片需要 `data_source_id`，通过新增的 `GET /api/admin/active-data-source` 端点获取（需后端配合实现）。

### 数据源管理流程

```
数据源列表（/datasources）
  → 点击 [+新建] → 抽屉表单 → POST /api/datasources → 刷新列表
  → 点击 [详情] → 数据源详情页（/datasources/[id]）
      → 基本信息（名称/引擎/host/port/状态）
      → 元数据概览（表数/列数）
      → 测试连接 → POST /{id}/test → 成功/失败提示
      → 激活/停用 → POST /{id}/activate|deactivate
      → 同步操作 → POST /{id}/sync → 轮询日志直到成功/失败
      → 学习操作 → POST /{id}/learn → 显示学习日志
      → 删除 → 二次确认 → DELETE /{id} → 跳转回列表
```

## 范围

### 范围内

#### 对话页 (/)

- SSE 流式查询（POST /api/query）
- 5 种消息气泡：文本 / SQL 块（可折叠+复制按钮）/ 确认卡片 / 结果表格 / 错误（含重试）
- 4 步进度条（idle/active/done/error）
- 会话管理：新建（POST /api/session）、列表渲染、切换加载历史（GET /api/conversations/{sid}）
- 空态快捷提示（点击示例查询 pill 填入输入框并发送）
- 输入区：Enter 发送 / Shift+Enter 换行 / 发送按钮运行时禁用+旋转

#### 管理控制台 (/admin)

- 同步状态卡片：最新同步信息 + 触发全量同步按钮 + 同步日志分页
- 知识图谱卡片：表/列/边标签式展示
- 值映射卡片：Tab 切换枚举/区域/名称 + 新增/删除
- 热词词典卡片：热词列表 + 新增/删除
- 固定日期周期卡片：周期列表 + 新增/删除
- 审核策略卡片：表单（mode/data_threshold/complexity_threshold）+ 统一保存按钮

#### 数据源管理 (/datasources, /datasources/[id])

- 数据源列表页：卡片式列表、新建/编辑抽屉（含表单校验）、测试连接、激活/停用、删除二次确认
- 数据源详情页：基本信息、元数据概览、同步操作（全量/按表）+ 同步日志、学习操作 + 学习日志、删除（含 Milvus/Neo4j 清理提示）

#### 全局

- 全局 Toast（操作成功绿色 / 失败红色 / 信息蓝色）
- 后端不可达时全局 Banner，禁用输入
- 响应式布局（Desktop ≥1024px / Tablet 768-1023px / Mobile <768px，侧边栏 overlay）

### 范围外

- 见「非目标」

## 功能需求

### 对话页

1. 用户输入 NL 文本并按 Enter 或点击发送 → 系统通过 SSE 流式返回进度和结果
2. 系统在查询执行期间展示 4 步进度条，当前阶段黄色脉动，已完成阶段绿色
3. 系统在收到 `need_confirm` 事件时展示确认卡片，列出待确认项
4. 用户在确认卡片中可点击确认或取消
5. 系统在收到 `result` 事件时展示结果表格（表头黄色、数据行深色）和 SQL 块（可折叠，带复制按钮）
6. 系统在收到 `error` 事件时展示红色错误卡片，含错误详情和重试按钮
7. 用户可创建新会话，会话列表显示在侧边栏
8. 用户可切换会话，切换后加载该会话的历史消息
9. 首次使用时显示空态快捷提示（4 个示例查询 pill）
10. 查询超时 60 秒后自动终止并显示"查询超时"提示

### 管理控制台

11. 管理员可查看最新同步状态，点击"触发全量同步"启动同步
12. 管理员可查看知识图谱概况（表/列/边数量与关系标签）
13. 管理员可在值映射卡片中按枚举/区域/名称 Tab 切换，新增或删除映射项
14. 管理员可在热词卡片中查看热词列表，新增或删除热词
15. 管理员可在固定日期周期卡片中新增或删除周期
16. 管理员可在审核策略卡片中修改策略并点击"保存设置"统一提交

### 数据源管理

17. 管理员可查看所有数据源，每个数据源显示名称、引擎、连接串、激活状态
18. 管理员可新建/编辑数据源（抽屉表单），含字段校验
19. 管理员可测试数据源连接，查看成功/失败结果
20. 管理员可激活/停用数据源
21. 管理员可在数据源详情页查看元数据概览（表数/列数）
22. 管理员可触发同步（全量或按表范围），查看同步日志
23. 管理员可触发元数据学习，查看学习日志
24. 管理员可删除数据源，删除前二次确认，成功后返回列表

### 异常处理

25. 页面加载时后端不可达 → 全局 Banner 警告，禁用输入框
26. SSE 中途断开 → 有内容时显示"连接中断"警告；无内容时显示错误+重试
27. 空结果（0 行）→ 显示"查询成功，但没有匹配的数据"（绿色，非红色）
28. 管理端单卡片 API 失败 → 仅该卡片显示错误+重试，其他卡片正常
29. 无激活数据源 → 图谱/值映射卡片显示空态引导文字
30. 审核策略保存成功 → Toast 提示"设置已保存（注意：服务重启后策略将恢复默认）"

## 业务规则

- 会话自动创建：首次查询无 `X-Session-Id` 时，后端自动创建并返回 header，前端保存 sessionId
- 管理端卡片独立加载：任一卡片 API 失败不影响其他卡片
- 删除操作必须二次确认（数据源删除 / 映射删除 / 热词删除 / 周期删除）
- 新建/编辑操作成功后自动刷新对应数据并显示成功 Toast
- 同步/学习触发后每 2 秒轮询状态，直到 success/failed，最多 30 次
- 审核策略保存为统一提交，非逐字段 PUT

## 边界情况与错误状态

- 后端 SSE 不区分 phase → 进度条降级为触发式推进，不做准确阶段映射
- need_confirm item 无 type → 统一文本列表渲染，不区分控件类型
- confirm/cancel 为 stub → 点击后仅更新 UI 文案，不期望后续 SSE 流
- 图谱端点需要 data_source_id → 前端先调 `GET /api/admin/active-data-source`（需后端新增），失败时显示无激活数据源空态
- 同步/学习正在运行时重复触发 → 后端返回 409，前端显示 Toast"已有任务运行中"

## 数据与状态

### Zustand Stores

**useChatStore**：
- `sessionId: string | null`
- `conversations: { id, title, time }[]`
- `messages: Message[]` — 当前会话的消息列表
- `queryState: 'idle' | 'running' | 'await_confirm'`
- `progressSteps: StepState[4]`

**useAdminStore**：
- `syncStatus`, `graphData`, `mappings`, `hotwords`, `periods`, `auditPolicy`
- 各卡片独立 loading/error 状态

**useDataSourceStore**：
- `dataSources: DataSource[]`
- `currentDetail: DataSourceDetail | null`

### API 端点依赖

| 前端页面 | 依赖端点 |
|---------|---------|
| 对话页 | `POST /api/query`, `POST /api/session`, `GET /api/conversations`, `GET /api/conversations/{sid}`, `POST /api/query/{id}/confirm`, `POST /api/query/{id}/cancel`, `GET /api/health` |
| 管理控制台 | `GET /api/admin/sync/status`, `GET /api/admin/sync/logs`, `POST /api/admin/sync/trigger`, `GET /api/admin/graph/nodes/{ds_id}`, `GET /api/admin/graph/edges/{ds_id}`, `GET /api/admin/mappings/{type}?data_source_id=`, `POST /api/admin/mappings/{type}`, `DELETE /api/admin/mappings/{type}/{id}`, `GET /api/admin/hotwords`, `POST /api/admin/hotwords`, `DELETE /api/admin/hotwords/{term}`, `GET /api/admin/fixed-periods`, `POST /api/admin/fixed-periods`, `DELETE /api/admin/fixed-periods/{name}`, `GET /api/admin/audit-policy`, `PUT /api/admin/audit-policy`, `GET /api/admin/active-data-source` **(需新增)** |
| 数据源管理 | `GET /api/datasources`, `POST /api/datasources`, `GET /api/datasources/{id}`, `PUT /api/datasources/{id}`, `DELETE /api/datasources/{id}`, `POST /api/datasources/{id}/test`, `POST /api/datasources/{id}/activate`, `POST /api/datasources/{id}/deactivate`, `GET /api/datasources/{id}/metadata`, `POST /api/datasources/{id}/sync`, `GET /api/datasources/{id}/sync-logs`, `POST /api/datasources/{id}/learn`, `GET /api/datasources/{id}/learning-logs` |

## 权限与合规

- V1 无认证：任何能访问前端和后端端口的人可使用全部功能
- 前端不存储密码：数据源密码通过后端加密，前端表单仅在提交时传输
- 查询结果不在前端持久化存储（仅内存中的 Zustand store，刷新后丢失）

## 发布与运营

### 迁移路径

1. `git rm frontend/chat.html` → 删除 HTML 原型
2. `cd frontend && pnpm create next-app@latest .` → Next.js 脚手架
3. 开发 3 页面 × 全部功能
4. `pnpm build` → Next.js standalone 模式输出
5. 更新 Docker Compose `web-ui` 服务指向 Next.js 构建产物
6. 删除 `chat.html` 引用 — git 历史保留可追溯

### 开发环境

- `pnpm dev`（frontend 目录）— Next.js dev server on port 3000
- `python main.py`（项目根目录）— FastAPI on port 8000
- 两个终端并行启动，无需统一脚本

### 环境变量

```
NEXT_PUBLIC_API_BASE=http://localhost:8000   # 开发
NEXT_PUBLIC_API_BASE=http://agent-api:8000   # Docker 生产
```

### Docker

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

## 实现决策

- **项目位置**：`frontend/` 目录，原地升级（先 `git rm chat.html`）
- **组件组织**：共享组件放 `components/shared/`，页面专属组件放路由旁 `_components/`
- **路由**：App Router — `/` 对话页、`/admin` 管理控制台、`/datasources` 列表、`/datasources/[id]` 详情
- **数据获取**：全客户端 `'use client'` + 浏览器直连 FastAPI，不做 BFF 层
- **SSE**：`@microsoft/fetch-event-source` 封装为 `useQuerySSE` hook，60s 超时（AbortController）
- **暗色主题**：统一使用 shadcn/ui 的 CSS 变量体系（`--background`/`--foreground`/`--primary` 等），在 `tailwind.config.ts` 中注入当前暗色主题色值
- **管理端 active-data-source**：需后端新增 `GET /api/admin/active-data-source` 返回 `{ data_source_id, name }`，前端在管理端 layout 层预取并注入子卡片

### 降级策略

| 功能 | 降级方案 |
|------|---------|
| 进度条阶段跟踪 | 触发式推进（收到第一个 status 后按固定间隔推进），不依赖后端 phase 字段 |
| 确认卡片按类型渲染 | 统一文本列表，不区分 time/enum/quantifier 控件 |
| 确认/取消 | 点击后仅更新 UI 文案（"已确认"/"已取消"），不期望后续 SSE |
| 图谱 active 端点 | 如后端未实现，降级为 GET /api/datasources 过滤 is_active |

## 测试决策

- 对话页端到端：模拟 SSE 流（Mock Service Worker 或后端 fixture），验证每种事件类型 → UI 渲染
- 管理控制台卡片：独立测试每张卡片的加载/空态/错误态
- 数据源 CRUD：测试新建→测试连接→激活→同步→查看日志→删除 全流程
- 异常路径：模拟后端不可达、SSE 中断、空结果、超时、409 冲突
- 验收标准（见下节）作为手工验收 checklist

## 验收标准

1. **对话页查询**：Given 已连接后端，When 输入"昨天的订单总数"并发送，Then SSE 流式返回 → 系统气泡依次显示进度 → 最终显示 SQL 块（可折叠、可复制）+ 结果表格 + 摘要文字
2. **会话自动创建**：Given 无 sessionId，When 发送第一条查询，Then 自动创建会话 → 侧边栏出现新会话项（标题为首条查询截断）
3. **会话切换**：Given 存在多个会话，When 点击切换到一个旧会话，Then 加载并渲染该会话的历史消息
4. **确认卡片**：Given 后端返回 need_confirm，When 收到事件，Then 气泡替换为确认卡片 → 列出待确认项 → 用户可点击确认或取消
5. **查询重试**：Given 查询失败显示错误卡片，When 点击重试按钮，Then 重新发起同一查询（SSE 流重新开始）
6. **管理端卡片独立**：Given 6 张卡片，When 其中 1 张的 API 返回 500，Then 仅该卡片显示错误+重试按钮，其余 5 张正常渲染
7. **审核策略保存**：Given 修改审核策略表单，When 点击「保存设置」，Then 统一提交 PUT → 成功显示绿色 Toast "设置已保存（注意：服务重启后策略将恢复默认）"
8. **数据源管理全流程**：Given 进入数据源列表，When 新建数据源 → 测试连接成功 → 激活 → 进入详情 → 触发同步 → 查看日志，Then 每个步骤返回正确的成功反馈
9. **删除二次确认**：Given 数据源详情页，When 点击「删除数据源」，Then 弹出确认对话框（含 Milvus/Neo4j 清理提示）→ 确认后执行删除 → 成功跳转回列表页
10. **后端不可达**：Given 后端未启动，When 页面加载，Then 显示全局 Banner "⚠ 无法连接到后端服务" → 输入框禁用 → 侧边栏仍可操作
11. **空结果**：Given 查询的 SQL 执行成功但返回 0 行，Then 显示绿色文字 "✅ 查询成功，但没有匹配的数据"（非红色错误）
12. **查询超时**：Given 后端 pipeline 执行超过 60 秒，Then 前端 AbortController 终止请求 → 显示"⏱ 查询超时" + 重试按钮
13. **无激活数据源空态**：Given 系统中无 is_active=true 的数据源，When 打开管理控制台，Then 图谱/值映射卡片显示"暂无激活的数据源，请在数据源管理中激活一个数据源"并提供跳转链接
14. **同步/学习 409 冲突**：Given 已有同步任务运行中，When 再次触发同步，Then 后端返回 409 → 前端显示 Toast"已有任务运行中"

## 开放问题

- **需后端新增端点**：`GET /api/admin/active-data-source` — 返回 `{ data_source_id, name }`。Owner: 后端。如未实现，前端降级为从 `GET /api/datasources` 过滤 `is_active:true`
- **SSE phase 字段**：后端需在 pipeline 各阶段发出 `phase` 字段。Owner: 后端。前端降级为触发式进度条
- **need_confirm type 字段**：后端需在 need_confirm items 中增加 `type`。Owner: 后端。前端降级为统一文本列表

## 补充说明

- **设计参考**：`docs/ui-interaction-design.md` — 完整的三页面 UI 交互规格、组件清单、设计 Token
- **后端接口**：`src/api/gateway.py`、`src/api/admin.py`、`src/api/datasources.py`
- **当前原型**：`frontend/chat.html`（开发完成后删除）
- **相关规格**：`team-spec/active/2026-06-19-api-gateway-chat-ui/`（API Gateway，Phase 9）、`team-spec/active/2026-06-19-admin-api/`（管理端 API，Phase 10）
- **风险与降级策略**：`team-spec/active/2026-06-19-chat-db-nextjs-frontend/spec/reviews.md`
