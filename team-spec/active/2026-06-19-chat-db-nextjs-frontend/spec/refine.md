# Chat-DB Next.js 前端重写 — 规格细化

- **slug**：`2026-06-19-chat-db-nextjs-frontend`
- **状态**：refining 完成（第 9 轮，review 反馈的 3 个 P1 问题均已确认）
- **基线**：`docs/ui-interaction-design.md`（UI 交互设计文档）；开发计划 Phase 9 延期部分 + Phase 10

## 需求复述

将 Chat-DB 前端从单文件 HTML 原型（`frontend/chat.html`，566 行）用 Next.js (App Router) 重写，覆盖 **对话页 / 管理控制台 / 数据源管理** 三个页面，详见 `docs/ui-interaction-design.md`。交付标准：功能增强（补齐原型缺失的交互缺陷 + 完整数据源管理）+ 替换上线（完成后删除 chat.html）。

## 规范术语

| 术语 | 定义 |
|------|------|
| 对话页 | 首页 `/`：NL 查询输入、SSE 流式响应、消息气泡、进度条、确认卡片、结果表格 |
| 管理控制台 | `/admin`：6 张功能卡片（同步状态/知识图谱/值映射/热词词典/固定日期周期/审核策略） |
| 数据源管理 | `/datasources` + `/datasources/[id]`：数据源 CRUD + 连接测试 + 激活/停用 + 元数据概览 + 同步/学习触发与日志 |
| SSE 流 | Server-Sent Events，`POST /api/query` 返回的 `text/event-stream` 响应，5 种事件类型 |
| 确认卡片 | 审核门触发的交互组件，根据 need_confirm item 类型渲染不同控件 |

## 范围内

### 页面功能

| 页面 | 功能 | 优先级 |
|------|------|--------|
| 对话页 `/` | SSE 流式查询、5 种消息气泡（文本/SQL/确认卡片/结果表格/错误）、4 步进度条、会话管理（新建/切换/历史回填）、快捷提示 | P0 |
| 管理控制台 `/admin` | 6 张卡片（同步状态含触发/日志分页、知识图谱 tags 展示、值映射 CRUD 含 Tab 切换、热词 CRUD、固定周期 CRUD、审核策略表单含统一保存） | P1 |
| 数据源列表 `/datasources` | 数据源卡片列表、新建/编辑抽屉表单、测试连接、激活/停用、删除二次确认 | P1 |
| 数据源详情 `/datasources/[id]` | 基本信息、元数据概览、同步操作（全量/按表）+ 日志、学习操作 + 日志、危险操作（删除含清理提示） | P1 |

### 功能增强（相比 chat.html 原型补齐）

1. **进度条阶段跟踪**：SSE status 事件区分 `semantic_matching` / `sql_generation` / `security_validation` / `execution` 四阶段（需后端配合增加 `phase` 字段，当前降级为触发式）
2. **确认卡片按类型渲染**：`time_normalized` 展示时间范围 / `enum_matched` 展示备选值可点击切换 / `quantifier_fuzzy` 提供输入框（需后端 need_confirm item 增加 `type` 字段）
3. **会话历史回填**：切换会话时调 `GET /api/conversations/{session_id}` 获取 turns 并渲染
4. **SQL 复制按钮**：SQL 块右上角一键复制
5. **查询重试**：错误气泡提供「重试」按钮
6. **管理端卡片重试**：单卡片 API 失败显示「重试」，不影响其他卡片
7. **审核策略统一保存**：改为「保存设置」按钮而非每个字段 change 即 PUT
8. **数据源管理完整页面**：当前完全缺失

### 技术选型（已确认）

| 决策项 | 选择 |
|--------|------|
| 框架 | Next.js 14+ App Router |
| 组件库 | shadcn/ui（基于 Radix + Tailwind CSS） |
| 状态管理 | Zustand（`useChatStore` / `useAdminStore` / `useDataSourceStore`） |
| SSE 消费 | `@microsoft/fetch-event-source` + 自定义 `useQuerySSE` hook |
| 数据获取 | 浏览器直连 FastAPI（`NEXT_PUBLIC_API_BASE` 环境变量） |
| 包管理 | pnpm |
| 代码检查 | ESLint（Next.js 内置 eslint-config-next） |
| 项目位置 | `frontend/`（原地升级，完成后删除 chat.html） |
| 文件组织 | 共享组件 `components/shared/`，页面专属组件路由旁 `_components/`，Zustand stores 统一 `stores/` |

### 异常处理（已确认）

| 场景 | 行为 |
|------|------|
| 后端不可达 | 气泡内红色错误 + "🔄 重试"按钮（重试 1 次） |
| SSE 中途断开 | 有内容则显示"连接中断"警告；无内容同不可达 |
| 查询超时（30s） | "⏱ 查询超时" + 重试按钮 |
| 空结果（0 行） | "✅ 查询成功，但没有匹配的数据"（非红色） |
| 健康检查失败（页面加载） | 全局 Banner "⚠ 无法连接到后端服务"，禁用输入，允许浏览历史 |
| 管理端单卡片失败 | 卡片级错误 + "重试"按钮，不影响其他卡片 |

### 补充决策（第 9 轮 review 反馈）

| 决策项 | 选择 |
|--------|------|
| 激活数据源 ID 获取 | **方案 B**：后端新增 `GET /api/admin/active-data-source`，返回 `{ data_source_id, name }`。前端调用此端点获取当前激活数据源 ID，再传给图谱/值映射等端点 |
| `frontend/` 目录处理 | **方案 A**：先 `git rm frontend/chat.html`，再 `create-next-app frontend`，保持原地升级 |
| 审核策略重启丢失 | **方案 A**：前端保存审核策略后 Toast 显示"注意：服务重启后策略将恢复默认" |
| Tailwind/设计 Token | 统一使用 shadcn/ui 的 CSS 变量体系（`--background` / `--foreground` / `--primary` 等），在 `tailwind.config.ts` 中映射覆盖为当前暗色主题色值 |

### 空态行为补充

| 场景 | 行为 |
|------|------|
| 无激活数据源 | 图谱卡片/值映射卡片显示"暂无激活的数据源，请在数据源管理中激活一个数据源"，提供跳转链接 |
| 无同步记录 | 同步状态卡片显示"暂无同步记录"，「触发全量同步」按钮仍然可用 |
| 无热词/周期/映射 | 对应卡片显示"暂无数据" + 新增按钮 |

## 范围外 / 延期

- D3.js 知识图谱可视化（V2，当前 tags 展示）
- 多步查询进度展示（依赖后端 `agents/graph.py` 实际执行，当前 dry-run）
- 审核断点续传（依赖后端 confirm/cancel 实际恢复/中止 pipeline，当前返回 acknowledged）
- 认证系统（V1 无认证）
- CSV/Excel 导出
- 移动端原生适配（响应式保证可用但不做移动端深度优化）
- 交互式图谱编辑（L3 人工补充，V2）

## 验收口径

1. 对话页：输入"昨天的订单总数" → SSE 流式返回 → 显示 SQL 块 + 结果表格 + 摘要文字
2. 对话页：无 sessionId 时自动创建 → 首次查询后侧边栏出现会话项
3. 对话页：切换会话 → 加载历史消息并渲染
4. 对话页：后端返回 `need_confirm` → 显示确认卡片（按 item type 渲染不同控件）
5. 对话页：点击重试 → 重新发起同一查询
6. 管理控制台：6 张卡片均可加载数据 → 新增/删除操作后刷新列表 → 操作成功/失败 Toast
7. 管理控制台：审核策略修改后点击「保存设置」统一提交，而非逐字段 PUT
8. 数据源管理：新建数据源 → 测试连接 → 激活 → 查看元数据概览 → 触发同步 → 查看日志
9. 数据源管理：删除数据源 → 二次确认对话框 → 成功后返回列表
10. 全局：页面加载时后端不可达 → 显示 Banner，禁用输入
11. 全局：管理端单卡片 API 失败 → 卡片内显示错误 + 重试，其他卡片正常工作

## 轻量风险扫尾

- **P1**：后端 SSE 当前不区分 phase（进度条只收到 `starting`）→ 前端降级为触发式进度条，后续后端增加 `phase` 字段后再联动
- **P1**：need_confirm item 当前无 `type` 字段 → 前端统一渲染为文本列表，后续后端增加 `type` 后丰富交互
- **P1**：confirm/cancel 端点当前为 stub → 确认卡片点击后仅更新 UI 文案，不期望后续 SSE
- **P1**：管理端图谱/值映射端点需要 `data_source_id`，但后端无 `GET /api/admin/active-data-source` → **已决议**：新增该端点（方案 B）。代码实锤——`chat.html:493` 调用 `/graph/nodes/active` 在 `admin.py:94` 的 `{data_source_id}` UUID 路径参数下必然返回 422
- **P2**：审核策略 `_AUDIT_POLICY` 为进程内存变量 → 前端保存后 Toast 提示"注意：服务重启后策略将恢复默认"
- **P2**：Docker Compose `web-ui` 服务需更新为 Next.js standalone 模式构建
- **P2**：开发环境两个终端（next dev + uvicorn），无统一启动脚本

## 开放问题（均已决议）

1. ~~范围边界~~ → 全部覆盖，对话页 P0 / 管理控制台 P1 / 数据源管理 P1
2. ~~技术选型~~ → App Router + shadcn/ui + Zustand + fetch-event-source + pnpm + 直连 FastAPI
3. ~~文件组织~~ → 混合策略（shared components + 路由旁 _components + stores/）
4. ~~数据获取策略~~ → 全客户端 + 浏览器直连，不做 BFF 代理
5. ~~完成标准~~ → 功能增强（补齐缺失交互）+ 替换上线
6. ~~异常处理~~ → 确认 6 种场景的具体行为
7. ~~构建部署~~ → pnpm + NEXT_PUBLIC_API_BASE + 标准 Dockerfile
8. ~~项目位置~~ → `frontend/` 原地升级
9. ~~激活数据源 ID 获取~~ → 方案 B：新增 `GET /api/admin/active-data-source` 端点
10. ~~`frontend/` 目录处理~~ → 方案 A：先 `git rm frontend/chat.html` 再 `create-next-app`
11. ~~审核策略重启丢失~~ → 方案 A：前端 Toast 提示

## Change Log

- 第 1 轮：确认范围 = 全部覆盖（对话 P0 / 管理 P1 / 数据源 P1）。
- 第 2 轮：确认技术选型 = App Router + shadcn/ui + `frontend/` 原地升级。
- 第 3 轮：确认数据获取 = 全客户端 + 浏览器直连。
- 第 4 轮：确认状态管理 = Zustand + fetch-event-source。
- 第 5 轮：确认完成标准 = 功能增强 + 替换上线。
- 第 6 轮：确认文件组织 = 混合策略。
- 第 7 轮：确认异常处理 = 6 种场景行为定稿。
- 第 8 轮：确认构建部署 = pnpm + 环境变量 + 标准 Dockerfile。收尾。
- 第 9 轮（review 反馈）：确认 active-data-source 端点方案、frontend 目录处理、审核策略提示；补充空态行为；P2 图谱风险升级 P1。
