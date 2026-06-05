# Harness Debt

> 记录阻碍 agent 独立工作的缺口。每条 debt 包含证据、影响、建议处理方式和优先级。

## 当前 Debt 清单

### DEBT-001: 覆盖率无门槛

- **证据**：`pyproject.toml` 中 `fail_under = 0`，无最低覆盖率要求
- **影响**：无法阻止低覆盖率代码合入
- **建议**：Phase 1 完成后设置 `fail_under = 60`，逐步提升
- **优先级**：中
- **建议转入技术债链路**：是（Phase 1 后）

### DEBT-002: mypy 未配置

- **证据**：mypy 在 dev 依赖中但无 `mypy.ini` 或 `pyproject.toml` 中的 mypy 配置
- **影响**：无法进行静态类型检查
- **建议**：添加 mypy 配置，至少对 `src/` 开启基本检查
- **优先级**：低（TDD 优先于类型检查）
- **建议转入技术债链路**：否（在 Phase 1-2 自然处理）

### DEBT-003: 无 CI 流水线

- **证据**：无 `.github/workflows/` 或其他 CI 配置
- **影响**：无法在 PR 时自动验证，依赖本地手动检查
- **建议**：添加 GitHub Actions，至少包含 pytest + ruff check
- **优先级**：中（首个 PR 前必须建立）
- **建议转入技术债链路**：是

### DEBT-004: 无 Docker Compose

- **证据**：`docs/development-plan.md` Phase 0 要求 Docker Compose 编排外部服务，但项目中不存在 `docker-compose.yml`
- **影响**：外部服务（PostgreSQL、Redis、Milvus、Neo4j）需要手动启动，无法一键搭建开发环境
- **建议**：创建 `docker-compose.yml`，至少包含 PG、Redis、Milvus、Neo4j
- **优先级**：高（Phase 1 开始连接外部服务前必须解决）
- **建议转入技术债链路**：是

### DEBT-005: 设计文档路径与实际代码路径不一致

- **证据**：`docs/development-plan.md` 使用 `backend/` 前缀（如 `backend/db/connection.py`），实际代码在 `src/` 下
- **影响**：agent 阅读设计文档后可能使用错误路径
- **建议**：在设计文档顶部添加路径映射说明，或在 harness 的 architecture-map.md 中明确标注
- **优先级**：低（已在 architecture-map.md 中标注，但设计文档本身未修正）
- **建议转入技术债链路**：否

### DEBT-006: README.md 命令与 CLAUDE.md 不一致

- **证据**：README.md 使用 `uv run pytest` 和 `uv run ruff`，CLAUDE.md 使用 `.venv/Scripts/python.exe -m pytest` 和 `.venv/Scripts/ruff.exe`
- **影响**：agent 可能使用错误的命令格式，尤其在 Windows 上
- **建议**：统一为 CLAUDE.md 中的写法（Windows 路径），或使用跨平台方案
- **优先级**：中
- **建议转入技术债链路**：否（直接修复即可）

### DEBT-007: 开发计划与实际技术栈不一致

- **证据**：`docs/development-plan.md` Phase 3 使用 ChromaDB，但 `pyproject.toml` 和 `.env.example` 使用 Milvus；Phase 9 提到 Next.js 前端，但项目无 frontend 目录
- **影响**：agent 阅读开发计划时可能做出错误的技术选择
- **建议**：以 pyproject.toml 和 .env.example 为准；在 development-plan.md 添加说明或更新文档
- **优先级**：中
- **建议转入技术债链路**：否（文档修正）

### DEBT-008: conftest.py 为空，缺少公共 fixture

- **证据**：`test/conftest.py` 只有 `import pytest`，无任何 fixture
- **影响**：每个测试文件需要独立 mock 外部服务，重复代码多
- **建议**：随着 Phase 1 实现，添加公共 fixture（如 mock LLM、mock DB 连接）
- **优先级**：中（Phase 1 开始实现时处理）
- **建议转入技术债链路**：否

---

## Debt 状态汇总

| ID | 优先级 | 状态 | 触发阶段 |
|----|--------|------|----------|
| DEBT-001 | 中 | 开放 | Phase 1 后 |
| DEBT-002 | 低 | 开放 | 自然消解 |
| DEBT-003 | 中 | 开放 | 首个 PR 前 |
| DEBT-004 | 高 | 开放 | Phase 1 前 |
| DEBT-005 | 低 | 已缓解 | — |
| DEBT-006 | 中 | 开放 | 随时可修 |
| DEBT-007 | 中 | 开放 | 随时可修 |
| DEBT-008 | 中 | 开放 | Phase 1 |

## 更新规则

- 每次遇到新卡点，添加新 debt 记录
- 已修复的 debt 标记为「已关闭」并注明关闭日期
- 重复出现的失败应考虑转入技术债链路（`team-tech-debt-refine`）
