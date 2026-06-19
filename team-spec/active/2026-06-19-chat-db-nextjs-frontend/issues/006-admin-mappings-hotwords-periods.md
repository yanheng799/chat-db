## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

管理控制台 `/admin` 页面的后 3 张 CRUD 卡片：值映射（枚举/区域/名称 Tab 切换）、热词词典、固定日期周期。每张卡片支持列表展示、新增和删除操作。

具体清单：
- `components/admin/MappingsCard.tsx`：
  - 顶部 Tab 切换：枚举 / 区域 / 名称
  - 加载：`GET /api/admin/mappings/{type}?data_source_id={ds_id}` → 列表展示（枚举：table.column = value → display + 别名 tag；区域：code → name + 别名；名称：short → full + target_table）
  - 「新增」按钮 → 抽屉表单（字段根据当前 Tab 类型动态变化） → `POST /api/admin/mappings/{type}`
  - 每条映射项的「删除」按钮 → 二次确认对话框 → `DELETE /api/admin/mappings/{type}/{item_id}`
  - 新增/删除成功后自动刷新列表 + Toast 提示
- `components/admin/HotwordsCard.tsx`：
  - 加载：`GET /api/admin/hotwords` → 列表展示（term → target_table.target_column / formula + 锁定图标）
  - 「新增」按钮 → 抽屉表单（term / target_table / target_column / formula / locked / description） → `POST /api/admin/hotwords`
  - 每条热词的「删除」按钮 → 二次确认对话框 → `DELETE /api/admin/hotwords/{term}`
- `components/admin/PeriodsCard.tsx`：
  - 加载：`GET /api/admin/fixed-periods` → 列表展示（name: start ~ end）
  - 「新增」按钮 → 抽屉表单（name / start_mmdd / end_mmdd） → `POST /api/admin/fixed-periods`
  - 每条周期的「删除」按钮 → 二次确认对话框 → `DELETE /api/admin/fixed-periods/{name}`

共享组件：
- `components/shared/ConfirmDialog.tsx`：通用二次确认弹窗（标题 + 描述 + 确认/取消按钮）
- 抽屉表单组件（可复用 shadcn/ui Sheet/Dialog）

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 打开管理控制台值映射卡片，When 切换 Tab 到「枚举」，Then 加载并显示枚举映射列表
- [ ] Given 值映射卡片「枚举」Tab，When 点击「新增」并填写 table_name/column_name/value/display/aliases → 提交，Then POST 成功后列表刷新 + Toast "映射已创建"
- [ ] Given 值映射列表中有条目，When 点击某条目的「删除」→ 弹出确认对话框 → 确认，Then DELETE 成功后该条目从列表消失 + Toast "映射已删除"
- [ ] Given 热词卡片，When 点击「新增」→ 填写 term/target_table/formula → 提交，Then 新热词出现在列表中
- [ ] Given 固定周期卡片，When 点击「新增」→ 填写 name/start_mmdd/end_mmdd → 提交，Then 新周期出现在列表中
- [ ] Given 热词列表中有一条热词，When 点击「删除」→ 确认，Then 热词消失
- [ ] Given 值映射 Tab 切换到「区域」，When 加载，Then 显示区域映射列表（与枚举列表结构不同但展示一致）

## Blocked by

- 001（nextjs-scaffold-shared-shell）

## Notes

- 值映射端点需要 `data_source_id` query param，与 Issue 005 共享 active data_source_id 获取逻辑
- 抽屉表单字段按 mapping_type 动态切换：枚举需要 table_name/column_name/value/display/aliases；区域需要 code/parent_code/level/name/aliases；名称需要 short_name/full_name/target_table/aliases
- 与 Issue 005 共享 `app/admin/page.tsx`——注意合并时避免冲突（可先约定卡片占位顺序：005 负责前 3 张，006 负责后 3 张）
- `ConfirmDialog` 为通用组件，放在 `components/shared/`，可被 Issue 007/008 的数据源删除复用
