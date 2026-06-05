# 编码规则

## 设计原则

三条核心原则，具体设计模式在实现时根据上下文选择：

### 1. 开闭原则（OCP）

- 新增匹配策略或标准化器时，**添加新类**，不修改已有的分发器
- 使用 strategy/plugin/protocol 模式扩展行为
- 典型场景：`semantic/matcher` 的四层匹配、`normalizer/` 的各标准化器

### 2. 依赖倒置（DIP）

- 依赖抽象（Protocol / Base Class），不依赖具体实现
- **必须**通过抽象接口访问：LLM、向量库、图数据库、缓存、数据库
- 接口定义在调用方包内，实现在基础设施包内

### 3. 单一职责（SRP）

- 每个模块/类做一件事
- 与 16 包结构对齐——如果一个模块做两件事，拆分
- 例如：`sql/` 拆为 generator、security、executor 三个文件

## 绝对禁止

- **禁止** `TODO`、`FIXME`、`pass`、`NotImplementedError`、`...` 等占位符
- **禁止**不完整的函数实现——每个函数必须有完整的工作代码
- **禁止**在 `.env` 中提交真实密钥
- **禁止**使用 `SELECT *` 生成的 SQL（设计规格要求）
- **禁止** LLM 动态编造业务指标公式（必须锁定在词典中）

## TDD 工作流（每个模块必须遵循）

```
1. 定义接口 → 分析职责，定义公共 API（函数签名、dataclass、Protocol）
2. 写测试（Red） → 在 test/ 对应子目录写测试用例，此时测试必须失败
3. 最小实现（Green） → 写最简单的代码让所有测试通过
4. 重构 → 在测试全绿的前提下清理代码，应用设计原则
5. 更新构建配置 → 如果新增了 src/ 下的包，添加到 pyproject.toml 的 packages 列表
```

### 测试目录约定

```
src/sql/security.py  →  test/test_sql/test_security.py
src/llm/client.py    →  test/test_llm/test_client.py
```

### 测试风格

- 使用 `pytest` + `pytest-asyncio`（`asyncio_mode = "auto"`）
- 异步测试直接写 `async def test_xxx()`，不需要额外装饰器
- 外部服务（LLM、向量库、图数据库、Redis、PostgreSQL）必须 mock
- 每个 test 文件顶部 import 被测模块的公共 API

## 配置管理

- **唯一配置源**：`.env` 文件（pydantic-settings）
- **禁止** YAML 配置文件
- 配置类放在 `src/config/`，继承 `pydantic_settings.BaseSettings`
- 新增配置项必须同步更新 `.env.example`

## 新增包检查清单

当在 `src/` 下新增子包时：

1. 创建 `src/{package}/__init__.py`
2. 在 `pyproject.toml` 的 `[tool.hatch.build.targets.wheel].packages` 添加 `"src/{package}"`
3. 创建对应测试目录 `test/test_{package}/`
4. 在 `docs/agent-harness/architecture-map.md` 更新包说明

## 提交规范

- 提交信息使用中文或英文均可，但需保持一致性
- 提交前必须通过 `ruff check --fix src/ && ruff format src/`
- 提交前必须通过 `pytest`

## 日志

- 使用 `structlog` 进行结构化日志
- 日志格式：JSON
- 关键节点（查询耗时、LLM 调用、错误）必须记录日志
- **禁止**使用 `print()` 替代日志

## 错误处理

- 使用自定义异常类，不直接 raise 内置异常
- 异常层级与包结构对齐（如 `sql/` 的异常在 `sql/exceptions.py` 中定义）
- 外部服务调用必须捕获异常并转换为领域异常
