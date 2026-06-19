from fastapi import FastAPI

from api.datasources import router as datasources_router
from api.admin import router as admin_router
from api.gateway import router as gateway_router

_DESCRIPTION = """
## Chat-DB — 自然语言数据库查询 Agent

通过对话式交互，使用日常口语甚至行业黑话查询数据库。
系统自动理解意图、标准化查询值、规划查询步骤、生成并执行只读 SQL。

### 模块
- **Gateway** — 查询入口（SSE 流式 / 会话管理 / 确认/取消）
- **Admin** — 管理端 API（同步 / 图谱 / 值映射 / 热词 / 审核策略）
- **Datasources** — 数据源 CRUD + 激活/同步/测试连接/元数据学习
"""

_TAGS = [
    {"name": "gateway", "description": "查询入口 — NL→SQL 流式管道 + 会话管理"},
    {"name": "admin", "description": "管理端 — 同步状态 / 图谱 / 值映射 / 热词 / 审核策略"},
    {"name": "datasources", "description": "数据源管理 — CRUD / 激活 / 同步 / 测试连接 / 元数据学习"},
]

app = FastAPI(
    title="Chat-DB",
    description=_DESCRIPTION,
    version="0.1.0",
    contact={"name": "yanheng", "url": "https://github.com/yanheng799/chat-db"},
    openapi_tags=_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.include_router(datasources_router)
app.include_router(gateway_router)
app.include_router(admin_router)
