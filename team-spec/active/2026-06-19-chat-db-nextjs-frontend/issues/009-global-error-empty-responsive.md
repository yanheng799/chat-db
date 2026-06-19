## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

全局基础设施收尾：统一异常处理、空态文案、Toast 通知系统、响应式布局。这些横切关注点影响所有页面，集中在一个 issue 中实现，确保一致的用户体验。

具体清单：
- `components/shared/GlobalBanner.tsx`：页面顶部全局 Banner 组件
  - 应用加载时 `GET /api/health` → 失败则显示 "⚠ 无法连接到后端服务 (localhost:8000)"，禁用输入框（通过 store 的 `backendUnreachable` 状态），允许浏览历史和管理端缓存数据
- `components/shared/Toast.tsx` + `stores/toast.ts`（或集成到各 store）：
  - 全局 Toast 容器（固定在右下角，堆叠显示）
  - 类型：success（绿色）/ error（红色）/ info（蓝色）
  - 自动消失：3 秒后淡出
  - 使用方式：`showToast({ type: 'success', message: '操作成功' })`
  - 在以下操作成功后触发：新建/编辑/删除数据源、新增/删除映射/热词/周期、审核策略保存、同步/学习触发
- 空态文案覆盖：
  - 管理端无激活数据源：图谱卡片 + 值映射卡片显示 "暂无激活的数据源，请在数据源管理中激活一个" + 跳转链接 → `/datasources`
  - 同步状态无记录："暂无同步记录"，「触发全量同步」按钮仍可用
  - 热词/周期/映射无数据：各自显示 "暂无数据" + 新增按钮
- 管理端卡片级错误处理（增强 Issue 005/006）：
  - 每张卡片独立 error 状态 → 仅该卡片显示 "加载失败" + 「重试」按钮
  - 重试仅重新请求该卡片的 API
- 响应式布局：
  - Desktop (≥1024px)：侧边栏常驻 280px
  - Tablet (768-1023px)：侧边栏可折叠（hamburger 按钮）
  - Mobile (<768px)：侧边栏 overlay 模式（backdrop + 左滑入），消息气泡 max-width 90%
  - 使用 Tailwind 响应式 class（`lg:` / `md:`）

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 后端未启动，When 页面加载（GET /api/health 失败），Then 显示全局 Banner "⚠ 无法连接到后端服务" → 输入框禁用 → 侧边栏仍可操作
- [ ] Given 任何成功的增/删/改操作，When 完成，Then 右下角弹出绿色 Toast → 3 秒后自动消失
- [ ] Given 任何失败的操作，When 完成，Then 右下角弹出红色 Toast 含错误原因
- [ ] Given 无激活数据源，When 打开管理控制台，Then 图谱和值映射卡片显示空态引导文字 + 跳转链接
- [ ] Given 管理端某卡片 API 返回错误，When 加载失败，Then 仅该卡片显示 "加载失败" + 重试按钮，其他卡片正常
- [ ] Given 移动端视口 (<768px)，When 点击 hamburger 按钮，Then 侧边栏以 overlay 模式从左侧滑入
- [ ] Given 移动端视口，When 点击侧边栏外部区域，Then 侧边栏关闭

## Blocked by

- 001（nextjs-scaffold-shared-shell）

## Notes

- Toast 用 Zustand store 管理队列：`toasts: { id, type, message }[]`，`showToast()` 添加 → 3 秒后 `removeToast(id)`。Toast 容器放 `app/layout.tsx`
- 健康检查在 `app/layout.tsx` 的 `useEffect` 中执行（客户端），结果存 `useChatStore.backendUnreachable`
- 响应式侧边栏状态（`sidebarOpen`）存 store，由 hamburger 按钮 + overlay 点击 + 路由切换 控制
- 此 issue 建议在所有页面功能完成后执行——确保覆盖全部空态和错误场景
