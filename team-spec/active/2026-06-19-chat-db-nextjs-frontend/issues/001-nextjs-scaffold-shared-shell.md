## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

初始化 Next.js 14+ 项目脚手架，搭建所有页面共享的基础设施：项目创建、依赖安装、Tailwind 暗色主题配置、共享 Shell 布局（侧边栏 + 主区域 + 模式切换）、API 客户端封装。最后删除旧 HTML 原型。

具体清单：
- `cd frontend && pnpm create next-app@latest .`（App Router + TypeScript + Tailwind CSS）
- `pnpm add zustand @microsoft/fetch-event-source`
- `npx shadcn@latest init`（暗色主题，CSS 变量体系映射当前项目色值：`--background: #060b14`、`--foreground: #e8ecf1`、`--primary: #f0b830` 等）
- `app/layout.tsx`：侧边栏（280px，Logo + 会话列表占位 + 底部三 Tab 模式切换按钮 [对话/管理/数据源]）+ 右侧主区域 `{children}`
- `lib/api.ts`：`const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'`，封装 `apiGet`/`apiPost`/`apiPut`/`apiDelete` 基础方法
- `stores/` 目录：创建 `chat.ts`、`admin.ts`、`datasources.ts` 三个 Zustand store 骨架（初始状态 + placeholder actions）
- 确认 `pnpm dev` 启动成功，`/`、`/admin`、`/datasources` 三个路由均可访问（空白占位）
- `git rm frontend/chat.html`，提交删除

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] Given 项目根目录，When `cd frontend && pnpm dev`，Then Next.js dev server 在 port 3000 启动成功 → **`pnpm build` + `pnpm dev` 均通过，3 路由 200**
- [x] Given 浏览器访问 `http://localhost:3000`，Then 显示带侧边栏的空白页面，侧边栏包含 Logo、会话列表区（空）、底部三个模式按钮 → **`app/layout.tsx` + `sidebar.tsx` 实现**
- [x] Given 点击侧边栏「管理」按钮，Then 主区域切换到 `/admin` 路由，侧边栏按钮高亮切换 → **`usePathname()` 驱动高亮**
- [x] Given 点击侧边栏「数据源」按钮，Then 主区域切换到 `/datasources` 路由 → **同机制**
- [x] Given 浏览器开发者工具检查样式，Then 页面使用暗色背景（`#060b14`）和 shadcn/ui 组件默认样式 → **`globals.css` 定制 oklch 暗色主题**
- [x] Given `git status`，Then `frontend/chat.html` 已删除 → **`git rm` 执行，565 行删除**

## Status

ready for PR

## Implementation Notes

- Next.js 16.2.9 (latest as of 2026-06-19, superseding 14 target)
- shadcn/ui 4.x (new-york defaults, no `--style` flag)
- Tailwind CSS 4.x with oklch color space
- pnpm 11.8.0
- Dark theme uses oklch equivalents: `--background: oklch(0.08 0.015 260)` ≈ `#060b14`, `--primary: oklch(0.78 0.16 85)` ≈ `#f0b830`
- 3 Zustand stores: `chat.ts` (session/messages/queryState), `admin.ts` (active ds + per-card loading/error), `datasources.ts` (full CRUD actions with API calls)

## Commands Run

| Command | Result |
|---------|--------|
| `pnpm build` | ✅ Compiled + TypeScript + 4 routes static generated |
| `pnpm dev` | ✅ Ready on :3000 in 747ms |
| `curl localhost:3000/` | ✅ 200 |
| `curl localhost:3000/admin` | ✅ 200 |
| `curl localhost:3000/datasources` | ✅ 200 |
| `git status` | ✅ `D frontend/chat.html`, clean scope |

## Findings

None. All 6 acceptance criteria verified.

## Regression Risks

- Low risk: `chat.html` prototype deleted; git history preserves it for reference
- Low risk: Next.js 16 may have API differences from 14 target; `page.tsx` uses `"use client"` directive which is standard

## Notes

- No `git commit` / `git push` executed
- `.env.local` contains `NEXT_PUBLIC_API_BASE=http://localhost:8000`
- `frontend/.gitignore` from Next.js template covers `node_modules/`, `.next/`

## Blocked by

None — can start immediately

## Notes

- 删除 `chat.html` 前确保 git 已提交当前状态（可回滚）
- shadcn/ui CSS 变量映射：当前项目自定义变量（`--bg-deep: #060b14` 等）→ 映射到 shadcn 体系（`--background`、`--foreground`、`--primary` 等），在 `app/globals.css` 和 `tailwind.config.ts` 中完成
- 侧边栏模式切换用 Next.js `useRouter` + `usePathname` 判断当前路由高亮
- `NEXT_PUBLIC_API_BASE` 默认值 `http://localhost:8000`
