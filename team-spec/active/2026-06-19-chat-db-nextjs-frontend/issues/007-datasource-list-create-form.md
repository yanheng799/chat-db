## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

数据源列表页 `/datasources`：卡片式展示所有已配置的数据源，支持新建/编辑（抽屉表单）、测试连接、激活/停用、删除操作。

具体清单：
- `app/datasources/page.tsx`：数据源列表页主组件
- `stores/datasources.ts`：`dataSources[]`、`loadDataSources()`、`createDataSource(data)`、`updateDataSource(id, data)`、`deleteDataSource(id)`、`testConnection(id)`、`activate(id)`、`deactivate(id)` actions
- `components/datasources/DataSourceCard.tsx`：单张数据源卡片，展示引擎图标（PostgreSQL/MySQL）、名称、连接串（host:port/database）、激活状态（绿点/灰点）、操作按钮行
- `components/datasources/DataSourceForm.tsx`：抽屉表单组件（基于 shadcn/ui Sheet），字段：名称*、引擎*(下拉 PostgreSQL/MySQL)、主机*、端口*、用户名*、密码*(带显示/隐藏切换)、数据库*、Schema 白名单(JSON 可选)
- 新建流程：点击侧边栏或页面 [+ 新建数据源] 按钮 → 打开空白抽屉表单 → 填写 → 「保存」→ `POST /api/datasources` → 201 → 关闭抽屉 → 刷新列表 + Toast
- 编辑流程：点击卡片 [编辑] → 打开预填抽屉表单（密码不回填，留空表示不修改）→ 「保存」→ `PUT /api/datasources/{id}` → 刷新列表 + Toast
- 测试连接：在表单中或卡片上点击 [测试连接] → `POST /api/datasources/{id}/test` → 显示结果（成功绿色 / 失败红色含 message）
- 激活/停用：卡片操作按钮根据 `is_active` 切换 → `POST /{id}/activate` 或 `/{id}/deactivate` → 刷新列表
- 删除：点击 [删除] → `ConfirmDialog`（复用 Issue 006 组件）→ 确认 → `DELETE /api/datasources/{id}` → 204 → 刷新列表 + Toast
- 表单校验：名称非空、引擎为 postgresql|mysql、host 非空、port 1-65535、username 非空、password 非空（新建时）、database 非空

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 打开 /datasources，When 加载完成，Then 显示所有数据源卡片，每张卡片含名称/引擎/host:port/database/激活状态
- [ ] Given 点击「新建数据源」，When 填写完整表单并保存，Then POST 成功 → 抽屉关闭 → 列表刷新 → 新数据源出现 + Toast
- [ ] Given 新建表单中名称留空，When 点击保存，Then 显示校验错误"名称不能为空"，不提交
- [ ] Given 已保存的数据源，When 点击「编辑」→ 修改名称 → 保存，Then PUT 成功 → 列表更新
- [ ] Given 数据源卡片，When 点击「测试连接」且后端可达，Then 显示绿色"连接成功"
- [ ] Given 未激活数据源，When 点击「激活」，Then POST activate 成功 → 卡片状态变为绿点"已激活"
- [ ] Given 已激活数据源，When 点击「停用」，Then POST deactivate 成功 → 卡片状态变为灰点
- [ ] Given 数据源卡片，When 点击「删除」→ 弹出确认对话框 → 确认，Then DELETE 成功 → 卡片消失 + Toast

## Blocked by

- 001（nextjs-scaffold-shared-shell）

## Notes

- 新建时「测试连接」按钮逻辑：需先保存数据源（拿到 id）再调 POST /{id}/test。或在表单中提供"保存并测试"按钮
- 密码字段：编辑时默认不显示（留空 = 不修改密码），新建时必填
- 表单校验在客户端做（端口范围、必填字段），服务端返回 409/422 时也显示对应错误
- 列表页「详情」链接指向 `/datasources/{id}`（Issue 008 实现）
