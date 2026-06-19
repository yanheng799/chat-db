## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

管理控制台 `/admin` 页面的前 3 张功能卡片：同步状态、知识图谱、审核策略。每张卡片独立加载、独立错误处理。

具体清单：
- `app/admin/page.tsx`：管理控制台主页面，垂直排列 6 张卡片（本 issue 实现前 3 张，后 3 张为占位空卡片）
- 获取 active data_source_id：优先调 `GET /api/admin/active-data-source`（需后端新增端点），如 404/未实现则降级为 `GET /api/datasources` → 过滤 `is_active: true` → 取第一条的 `id`
- `components/admin/SyncStatusCard.tsx`：
  - 加载：`GET /api/admin/sync/status` → 展示最新同步信息（类型/状态/时间/新增表/删除表/变更列）
  - 「触发全量同步」按钮 → `POST /api/admin/sync/trigger` → 按钮变为 "同步中…" disabled → 每 2 秒轮询 `GET /api/admin/sync/status` 直到 status 为 success/failed，最多 30 次（60 秒）
  - 同步日志分页：`GET /api/admin/sync/logs?limit=20`
- `components/admin/GraphCard.tsx`：
  - 加载：`GET /api/admin/graph/nodes/{ds_id}` + `GET /api/admin/graph/edges/{ds_id}` → 标签式展示（表/列 tag + 关系边 tag 前 10 条）
  - 统计摘要：N 表 / M 列 / K 边
- `components/admin/AuditPolicyCard.tsx`：
  - 加载：`GET /api/admin/audit-policy` → 表单（mode 下拉选择 none/high_risk/all、data_threshold 数字输入、complexity_threshold 数字输入）
  - 「保存设置」按钮 → `PUT /api/admin/audit-policy` → 成功后 Toast "设置已保存（注意：服务重启后策略将恢复默认）"

每张卡片有独立 loading/error 状态：加载中显示骨架屏，失败显示红色错误 + 重试按钮。一张卡片失败不影响其他卡片。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 有激活数据源，When 打开 /admin 页面，Then 同步状态卡片显示最新同步记录；图谱卡片显示表/列/边统计 + 关系标签；审核策略卡片显示当前配置表单
- [ ] Given 点击「触发全量同步」，Then 按钮变为 disabled "同步中…" → 每 2 秒轮询状态 → 完成后显示 success 并刷新同步信息
- [ ] Given 同步轮询超过 60 秒（30 次），Then 停止轮询 → 显示 "同步超时，请手动刷新"
- [ ] Given 在审核策略表单中修改 mode 为 high_risk，When 点击「保存设置」，Then 调 PUT 提交全部字段 → 成功显示绿色 Toast 含重启丢失提示
- [ ] Given 图谱卡片 API 返回错误，When 渲染失败，Then 仅该卡片显示红色错误 + 重试按钮，同步和审核卡片正常工作
- [ ] Given 同步状态卡片首次加载，When API 请求中，Then 显示骨架屏而非空白

## Blocked by

- 001（nextjs-scaffold-shared-shell）

## Notes

- **关键**：图谱端点路径参数是 UUID（`/graph/nodes/{data_source_id}`），不能传 `"active"` 字符串——FastAPI 会返回 422。必须先获取实际 data_source_id
- **需后端新增端点**：`GET /api/admin/active-data-source` 返回 `{ data_source_id, name }`。如未实现，降级为 `GET /api/datasources` → `find(ds => ds.is_active)?.id`
- 审核策略 `_AUDIT_POLICY` 为进程内存变量（`admin.py:274`），重启丢失
- 同步轮询间隔 2s，最多 30 次
- 与 Issue 006 共享 `app/admin/page.tsx` 页面布局和 active data_source_id 获取逻辑
