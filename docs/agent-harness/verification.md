# 验证策略

## 按变更类型的最低验证要求

### 新增模块/包

```bash
# 1. 新增包必须已加入 pyproject.toml
grep "src/{new_package}" pyproject.toml

# 2. 测试目录已创建
ls test/test_{new_package}/

# 3. 全部测试通过
.venv/Scripts/python.exe -m pytest

# 4. 新模块被正确导入
.venv/Scripts/python.exe -c "import {new_package}"
```

### 修改现有模块

```bash
# 1. 该模块的测试通过
.venv/Scripts/python.exe -m pytest test/test_{module}/

# 2. 全量测试通过（确保无回归）
.venv/Scripts/python.exe -m pytest

# 3. Lint 通过
.venv/Scripts/ruff.exe check src/

# 4. 格式化无变化
.venv/Scripts/ruff.exe format --check src/
```

### 修改配置（.env / pyproject.toml / pydantic-settings）

```bash
# 1. 配置可正常加载
.venv/Scripts/python.exe -c "from config import Settings; print(Settings())"

# 2. 全量测试通过
.venv/Scripts/python.exe -m pytest
```

### 修改测试

```bash
# 1. 被测模块的测试通过
.venv/Scripts/python.exe -m pytest test/test_{module}/ -v

# 2. 无意外的 import 错误
.venv/Scripts/python.exe -m pytest --co
```

### 文档变更

- 人工检查链接有效性
- 人工检查与实际代码的一致性

## 快速本地验证 vs 完整回归验证

### 快速本地验证（每次变更后，< 30 秒）

```bash
.venv/Scripts/ruff.exe check --fix src/ && .venv/Scripts/ruff.exe format src/
.venv/Scripts/python.exe -m pytest test/test_{changed_module}/ -v
```

### 完整回归验证（提交前 / PR 合并前）

```bash
.venv/Scripts/ruff.exe check src/
.venv/Scripts/ruff.exe format --check src/
.venv/Scripts/python.exe -m pytest --cov=src --cov-report=term-missing
```

## 不可自动验证的检查项

以下需要人工审查：

1. **OCP 合规**：新增行为是否通过扩展而非修改实现
2. **DIP 合规**：是否通过抽象接口访问外部依赖
3. **SRP 合规**：模块是否保持单一职责
4. **无占位符**：确认代码中无 TODO/FIXME/pass/NotImplementedError
5. **TDD 顺序**：确认测试先于实现编写（从 git history 可见）
6. **接口设计**：公共 API 是否简洁、命名是否一致
7. **.env.example 同步**：新增配置项是否已更新到 .env.example

## 当前验证能力状态

| 检查项 | 状态 | 说明 |
|--------|------|------|
| pytest | ✅ 可用 | 当前零测试，框架已就绪 |
| ruff check | ✅ 可用 | 当前零代码，框架已就绪 |
| ruff format | ✅ 可用 | 当前零代码，框架已就绪 |
| 覆盖率门禁 | ❌ 未启用 | `fail_under = 0`，无最低覆盖率要求 |
| mypy 类型检查 | ⚠️ 未配置 | mypy 在 dev 依赖中但无配置文件 |
| CI 流水线 | ❌ 不存在 | 无 .github/workflows 或其他 CI 配置 |
| 服务启动验证 | ❌ 不可用 | api/ 为空，服务无法启动 |
