# 开发命令手册

## 前置条件

- **Python**：>= 3.11，系统路径 `D:/Python/Python311/python.exe`
- **uv**：通过系统 Python 安装，不在 venv 内
- **网络**：PyPI 不可靠，**必须**使用清华镜像 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`
- **.env 文件**：从 `.env.example` 复制并填写。`.env` 已 gitignore

## 依赖安装

```bash
# 安装全部依赖（含 dev）
python -m uv sync --extra dev --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 仅安装运行时依赖
python -m uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

- **适用场景**：首次 clone、切换分支后 lock 文件变化时、添加新依赖后
- **预期耗时**：首次 2-5 分钟，增量 10-30 秒
- **常见失败**：网络超时 → 重试，或确认镜像 URL 正确

### 添加新依赖

```bash
# 添加运行时依赖
python -m uv add <package> --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 添加开发依赖
python -m uv add --dev <package> --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

添加后必须检查 `pyproject.toml` 中依赖是否正确记录。

## 测试

```bash
# 运行全部测试
.venv/Scripts/python.exe -m pytest

# 运行单个模块测试
.venv/Scripts/python.exe -m pytest test/test_config/

# 运行单个测试用例
.venv/Scripts/python.exe -m pytest test/test_config/test_settings.py::test_x

# 带覆盖率
.venv/Scripts/python.exe -m pytest --cov=src --cov-report=term-missing

# 只运行失败的测试（pytest-xdist 不可用时的替代）
.venv/Scripts/python.exe -m pytest --lf

# 详细输出
.venv/Scripts/python.exe -m pytest -v
```

- **适用场景**：每次代码变更后
- **预期耗时**：当前零测试，< 1 秒；随着测试增加，预计全量 < 30 秒
- **异步测试**：`pytest-asyncio` 已配置 `asyncio_mode = "auto"`，async 函数直接写即可
- **当前状态**：`fail_under = 0`，无覆盖率门槛；后续应提高

### 测试目录约定

```
test/
  test_{module}/
    test_{file}.py
```

例如 `src/sql/security.py` → `test/test_sql/test_security.py`

## Lint 与格式化

```bash
# 检查代码问题
.venv/Scripts/ruff.exe check src/

# 自动修复
.venv/Scripts/ruff.exe check --fix src/

# 格式化
.venv/Scripts/ruff.exe format src/

# 检查 + 格式化一步到位
.venv/Scripts/ruff.exe check --fix src/ && .venv/Scripts/ruff.exe format src/
```

- **Ruff 配置**：target Python 3.11, line-length 120, lint rules: E, F, I, N, UP, B, SIM
- **适用场景**：每次提交前
- **预期耗时**：< 5 秒

### 类型检查（可选）

```bash
.venv/Scripts/python.exe -m mypy src/
```

目前 mypy 在 dev 依赖中但无配置文件，需要后续配置。

## 运行服务

```bash
# 启动 API 服务（开发模式，热重载）
.venv/Scripts/python.exe -m uvicorn api.main:app --reload
```

- **前置条件**：`.env` 配置正确，外部服务（PostgreSQL、Redis 等）已运行
- **当前状态**：`src/api/__init__.py` 为空，服务尚不可启动
- **端口**：默认 8000

## 外部服务依赖

以下服务需要本地运行或远程可达，但**不在本项目代码中管理**：

| 服务 | 默认地址 | .env 变量前缀 |
|------|----------|---------------|
| PostgreSQL | 127.0.0.1:5432 | `POSTGRES_*` |
| Redis | 127.0.0.1:6379 | `REDIS_*` |
| Milvus | 127.0.0.1:19530 | `MILVUS_*` |
| Neo4j | bolt://127.0.0.1:7687 | `NEO4J_*` |
| Embedding 服务 | http://127.0.0.1:8001/v1 | `EMBEDDING_*` |
| DashScope API | 远程 | `DASHSCOPE_API_KEY` |

当前无 Docker Compose 配置，需要手动启动这些服务。

## 构建与打包

```bash
# 构建 wheel
.venv/Scripts/python.exe -m uv build
```

- **重要**：新增 `src/` 下的包时，必须在 `pyproject.toml` 的 `[tool.hatch.build.targets.wheel].packages` 中添加

## 禁止事项

- **禁止**使用 `uv run` 命令（README.md 中的写法已过时，Windows 下应使用 `.venv/Scripts/python.exe -m`）
- **禁止**不加 `--index-url` 直接安装依赖
- **禁止**在 `.env` 中提交真实密钥
