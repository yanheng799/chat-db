# Chat-DB

自然语言数据库查询 Agent 系统 —— 通过对话式交互，使用自然语言查询数据库。

## 快速开始

### 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd chat-db

# 创建虚拟环境并安装依赖
uv sync --extra dev
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入真实配置
```

### 运行

```bash
# 启动 API 服务
uvicorn api.main:app --reload

# 运行测试
uv run pytest

# 代码检查
uv run ruff check src/
uv run ruff format src/
```

## 项目结构

```
chat-db/
├── src/                  # 源码
│   ├── config/           # 配置管理
│   ├── llm/              # LLM 调用抽象层
│   ├── db/               # 数据库连接层
│   ├── metadata/         # 元数据提取与同步
│   ├── learning/         # 元数据学习 (L0-L2)
│   ├── knowledge/        # Milvus + Neo4j + 热词 + 值映射
│   ├── normalizer/       # 查询值标准化
│   ├── semantic/         # 四层语义匹配
│   ├── sql/              # SQL 生成/校验/执行
│   ├── pipeline/         # 单步/多步查询串联
│   ├── agents/           # LangGraph 多 Agent 编排
│   ├── healing/          # 错误自愈
│   ├── memory/           # 会话管理与缓存
│   ├── profile/          # 用户特征
│   ├── api/              # FastAPI Gateway
│   └── utils/            # 通用工具
├── test/                 # 测试（镜像 src 结构）
├── docs/                 # 文档
├── pyproject.toml        # 项目配置
└── .env.example          # 环境变量模板
```

## 技术栈

- **Agent 编排**: LangGraph
- **LLM**: LangChain + DeepSeek/Qwen
- **向量库**: Milvus 2.6+
- **图数据库**: Neo4j
- **缓存**: Redis
- **元数据库**: PostgreSQL
- **Web 框架**: FastAPI
- **数据库连接**: SQLAlchemy 2.0 (async)

## License

MIT
