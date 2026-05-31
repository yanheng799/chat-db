# 自然语言数据库查询 Agent 系统 — 开发计划

> 基于 `docs/自然语言数据库查询需求设计.md`（V5.0 最终精简版）分析生成
>
> 生成日期：2026-05-31

---

## 总览

| 阶段 | 名称 | 预计天数 | 依赖 |
|------|------|----------|------|
| Phase 0 | 项目脚手架与基础设施 | 2-3 天 | — |
| Phase 1 | 数据源连接与元数据提取 | 3-4 天 | Phase 0 |
| Phase 2 | 元数据学习（Level 0-2） | 4-5 天 | Phase 1 |
| Phase 3 | 知识库构建 | 5-6 天 | Phase 2 |
| Phase 4 | 查询值标准化 | 4-5 天 | Phase 3 |
| Phase 5 | 语义匹配 + 单步查询核心链路 | 4-5 天 | Phase 3, Phase 4 |
| Phase 6 | 多 Agent 编排（LangGraph） | 5-7 天 | Phase 5 |
| Phase 7 | 错误自愈系统 | 3-4 天 | Phase 6 |
| Phase 8 | 上下文记忆与用户特征 | 3-4 天 | Phase 6 |
| Phase 9 | API Gateway + Web Chat UI | 5-7 天 | Phase 8 |
| Phase 10 | 管理端界面 | 4-5 天 | Phase 9 |
| Phase 11 | 生产加固 | 3-5 天 | Phase 10 |

- **首个可演示里程碑**：Phase 5 完成（单步 NL 查询端到端），累计约 **18-22 天**
- **完整 MVP**：Phase 9 完成（Web Chat 全流程），累计约 **38-49 天**
- **生产就绪**：Phase 11 完成，累计约 **45-59 天**

---

## 依赖关系图

```
Phase 0 (脚手架)
  └─→ Phase 1 (元数据提取) ──→ Phase 2 (元数据学习) ──→ Phase 3 (知识库)
                                                              │
                                                              ├─→ Phase 4 (值标准化) ──┐
                                                              │                         │
                                                              └─→ Phase 5 (语义匹配) ──┤
                                                                                        │
                                                                  Phase 5 (单步链路) ←─┘
                                                                        │
                                                                        └─→ Phase 6 (多Agent) ──→ Phase 7 (错误自愈)
                                                                                                      │
                                                                                        ┌─────────────┘
                                                                                        ▼
                                                                              Phase 8 (记忆+用户特征)
                                                                                        │
                                                                                        ▼
                                                                                  Phase 9 (API+Chat UI)
                                                                                        │
                                                                                        ├─→ Phase 10 (管理端)
                                                                                        │
                                                                                        └─→ Phase 11 (生产加固)
```

---

## Phase 0 — 项目脚手架与基础设施（2-3 天）

### 0.1 项目 Monorepo 结构搭建

- 创建 `backend/` Python 项目（`pyproject.toml`、`uv.lock`）
- 创建 `frontend/` Next.js 项目（`package.json`、`tsconfig.json`）
- 共享配置目录 `shared/`
- `.gitignore`、`.env.example`、`README.md`

### 0.2 Docker Compose 编排

服务清单：

| 服务 | 用途 |
|------|------|
| `postgres` | 用户画像、审计日志、查询历史、值映射配置、元数据变更日志 |
| `redis` | 会话状态、查询结果缓存 |
| `neo4j` | 表关系图谱、同义边、JOIN 频次 |
| `chromadb` | 字段语义向量、查询样例向量 |
| `agent-api` | 后端 API（FastAPI） |
| `web-ui` | 前端 Next.js |
| `metadata-syncer` | 元数据定时同步 Worker |

### 0.3 配置管理系统

- 环境变量 + YAML 配置文件
- 数据库连接串、LLM 配置、审核策略默认值
- 环境区分（dev / staging / prod）

### 0.4 LLM 调用抽象层

- 统一接口：`llm.chat()`、`llm.stream()`、`llm.embed()`
- 支持 DeepSeek / Qwen
- 内置重试、超时、Token 计数

### 0.5 日志与基础监控埋点

- 结构化日志（JSON 格式）
- 关键节点埋点（查询耗时、LLM 调用次数、错误计数）
- 与监控指标的对接点预留

> **检查点**：`docker compose up` 所有服务正常启动，LLM 能调通

---

## Phase 1 — 数据源连接与元数据提取（3-4 天）

### 1.1 只读数据库连接层

- SQLAlchemy 连接管理
- 强制只读：`SET TRANSACTION READ ONLY`
- 资源限制：`max_execution_time` / `statement_timeout`
- 连接池配置

**产出**：`backend/db/connection.py`

### 1.2 information_schema 全量提取器

- 表信息：表名、注释、行数
- 字段信息：字段名、类型、是否可空、默认值、注释、是否主键
- 索引信息
- 外键信息（显式声明的）

**产出**：`backend/metadata/extractor.py`

### 1.3 元数据存储

- PostgreSQL 数据模型设计
  - `schemas`、`tables`、`columns`、`indexes`、`foreign_keys`
  - `metadata_snapshots`、`metadata_change_log`
- 全量快照 + 增量变更日志

**产出**：`backend/metadata/store.py` + 数据模型

### 1.4 元数据同步引擎

- 定时巡检（每天凌晨全量扫描）
- Schema Diff 计算（新增表/字段、删除表/字段、类型变更）
- 变更通知（日志 + 可选告警）

**产出**：`backend/metadata/sync_engine.py`

> **检查点**：能连接真实数据库，提取完整 schema，存入 PG，检测结构变更

---

## Phase 2 — 元数据学习（Level 0-2）（4-5 天）

> 文档 §七：四层递进架构。V1 实现 L0-L2，L3（人工补充）留到管理端。

### 2.1 Level 0：Schema 直接提取

- 从 information_schema 提取注释、类型、主键
- 若有列注释，直接作为字段语义描述的最佳来源
- 来源标记：`source = "schema_comment"`

**产出**：`backend/learning/level0_extract.py`

### 2.2 Level 1：规则推断

- 字段名拆词：`order_status` → "订单状态"、`created_at` → "创建时间"
  - CamelCase / snake_case 拆分
  - 中英文对照词表
- 数据模式检测：
  - 值分布分析（枚举字段识别）
  - NULL 比例分析
  - 数值范围分析
- 值重叠度外键推断：
  - 跨表字段值重叠率 > 阈值 → 推断潜在外键
  - 结合字段名相似度评分
- 来源标记：`source = "rule_inference"`

**产出**：`backend/learning/level1_rules.py`

### 2.3 Level 2：LLM 语义推断

- 脱机批量处理（不阻塞用户请求）
- 输入：表名 + 字段名 + 类型 + 采样数据
- 输出：字段业务含义、表业务含义、可能的枚举值语义
- 批量调用 LLM（控制并发 + 成本）
- 来源标记：`source = "llm_inference"`

**产出**：`backend/learning/level2_llm.py`

### 2.4 学习编排器

- L0 → L1 → L2 串联
- 上层已有结果则跳过（置信度足够时不覆盖）
- 学习结果汇总存储

**产出**：`backend/learning/orchestrator.py`

> **检查点**：每张表/字段都有语义描述（来源标注 L0/L1/L2），外键关系推断完成

---

## Phase 3 — 知识库构建（5-6 天）

> 文档 §二 2.2 数据存储职责边界

### 3.1 向量库（ChromaDB）

- Collection: `field_descriptions` — 字段语义描述向量化
- Collection: `query_samples` — 查询样例向量化（热启动）
- 嵌入模型集成（与 LLM 抽象层统一）
- 基本 CRUD + 增量更新

**产出**：`backend/knowledge/vector_store.py`

### 3.2 图数据库（Neo4j）

- 数据模型：
  ```cypher
  (:Table {name, row_count})
  (:Column {name, type, is_pk, nullable})
  (:Table)-[:CONTAINS]->(:Column)
  (:Column)-[:REFERENCES {confidence}]->(:Column)
  (:Column)-[:INFERRED_REF {confidence}]->(:Column)
  (:Column)-[:SAME_MEANING {reason}]->(:Column)
  (:Table)-[:JOINS_WITH {frequency}]->(:Table)
  ```
- 建图脚本：从元数据学习结果构建全图
- 增量更新：元数据变更时同步更新

**产出**：`backend/knowledge/graph_store.py` + Cypher 脚本

### 3.3 图谱查询能力

- 最短 JOIN 路径查找：
  ```cypher
  MATCH path = shortestPath(
    (a:Table {name: 'orders'})-[*..3]-(b:Table {name: 'customers'})
  ) RETURN path
  ```
- 关联表查找（按字段语义搜索 + 图关系过滤）
- JOIN 频次统计与排序

**产出**：`backend/knowledge/graph_query.py`

### 3.4 热词词典

- 数据模型：术语 → 字段映射（一对多）
- 业务指标公式（锁定机制，禁止 LLM 动态编造）：
  ```json
  {
    "term": "销售额",
    "formula": "SUM(price * quantity)",
    "table": "orders",
    "locked": true
  }
  ```
- 固定日期型周期配置（双十一、618 等）
- REST API：CRUD + 批量导入

**产出**：`backend/knowledge/hot_words.py` + API

### 3.5 值映射中心

- 枚举别名映射：
  ```json
  {
    "table": "orders",
    "column": "status",
    "mappings": [
      {"value": "completed", "aliases": ["已完成", "完结", "结了"], "display": "已完成"}
    ]
  }
  ```
- 区域字典（省/市/区 + 别名 + 层级关系）
- 名称简称映射（客户简称 → 全称、产品简称 → 全称）

**产出**：`backend/knowledge/value_mapping.py` + API

> **检查点**：向量搜索返回语义相关字段，图谱能查询 JOIN 路径，词典/值映射可 CRUD

---

## Phase 4 — 查询值标准化（4-5 天）

> 文档 §四：查询值标准化系统

### 4.1 统一数据结构

```python
@dataclass
class NormalizedValue:
    original: str            # 用户原始输入
    normalized: Any          # 标准化后的值
    value_type: str          # time/enum/region/name
    db_representation: Any   # 数据库可直接使用的值（SQL 片段）
    confidence: float        # 置信度
    matched_by: str          # 匹配策略
    need_confirm: bool       # 是否需要用户确认
    alternatives: list       # 候选值
```

**产出**：`backend/normalizer/types.py`

### 4.2 时间表述标准化

- 标准相对时间：今天/昨天/本周/上周/本月/上月/本季度/今年
- 绝对时间：2026年5月、2026-05-01、2026-05-01 09:00
- 固定日期型自定义周期（仅固定日期，不含计算型）：
  ```python
  FIXED_DATE_PERIODS = {
      "双十一": {"start": "11-01", "end": "11-11"},
      "618": {"start": "06-01", "end": "06-18"},
  }
  ```
- 明确排除：财年、农历、动态相对周期 → 引导用户用绝对日期

**产出**：`backend/normalizer/time_parser.py`

### 4.3 枚举值映射

策略优先级：
1. 字典表实时查询（如有外键关联字典表）
2. 精确匹配 display_name
3. 别名匹配（aliases 数组）
4. 编辑距离模糊匹配（阈值 0.7）
5. LLM 兜底理解（最后的策略，confidence > 0.85 才采纳）

**产出**：`backend/normalizer/enum_matcher.py`

### 4.4 区域/地名处理

- 粒度自适应：
  - "华东" → 区域维度
  - "上海" → 城市维度
  - "浦东" → 区级维度
- 层级包含关系统一为 SQL IN 子句

**产出**：`backend/normalizer/region_parser.py`

### 4.5 名称简称匹配

7 策略递进：
1. 精确匹配
2. 简称匹配（首字母缩写、常见简称）
3. 别名匹配（别名表）
4. 拼音匹配（拼音全拼/首字母）
5. 关键字匹配（分词后子串匹配）
6. 编辑距离（阈值 0.7）
7. 向量语义匹配（embedding 相似度）

全部失败 → 源库实时模糊查询（`LIKE '%xxx%'`）→ 异步学习新映射

**产出**：`backend/normalizer/name_matcher.py`

### 4.6 数值范围处理

- 模糊量词检测：`['高价值', '大额', '小额', '适中', '大量', '少量']`
- 检测到 → 返回追问，不自动量化

**产出**：`backend/normalizer/quantifier.py`

> **检查点**：输入 "上周北京已完成的订单"，输出结构化标准化结果

---

## Phase 5 — 语义匹配 + 单步查询核心链路（4-5 天）

> 文档 §八 + §十 + §三 3.1 正常流程。**首次可演示里程碑。**

### 5.1 四层语义匹配

1. 热词词典（确定性映射，含锁定业务指标）
2. 行业词库（领域术语 → 字段映射）
3. 向量检索（语义相似度 top-k）
4. LLM 翻译（兜底理解，标注 `source = "llm_fallback"`，触发强制审核）

**产出**：`backend/semantic/matcher.py`

### 5.2 单步 SQL 生成

- LLM Prompt：Schema 上下文 + 标准化值 + 语义匹配结果 + 用户原句
- 约束注入：只读、LIMIT、禁止 SELECT *
- 输出：SQL 语句 + 置信度 + 解释

**产出**：`backend/sql/generator.py`

### 5.3 安全校验

- **黑名单**：禁止 `INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|EXEC|INTO OUTFILE|LOAD|SLEEP|BENCHMARK|@@version`
- **白名单**：强制 `LIMIT ≤ 1000`、禁止 `SELECT *`
- 语法校验（`sqlparse` 解析检查）

**产出**：`backend/sql/security.py`

### 5.4 SQL 执行

- 只读连接 + 超时控制
- 结果捕获（列名 + 数据行）
- 执行耗时记录

**产出**：`backend/sql/executor.py`

### 5.5 单步查询完整串联

```
用户输入
  → 值标准化 (Phase 4)
  → 语义匹配 (§5.1)
  → SQL 生成 (§5.2)
  → 安全校验 (§5.3)
  → [审核阻断 - 若需要]
  → SQL 执行 (§5.4)
  → 自然语言结果总结 (LLM)
  → 返回用户
```

**产出**：`backend/pipeline/single_step.py`

> **检查点**：输入 "查一下昨天的订单总数" 能端到端返回正确结果
>
> **这是首次可演示的里程碑。**

---

## Phase 6 — 多 Agent 编排（LangGraph）（5-7 天）

> 文档 §三：多 Agent 协作流程

### 6.1 LangGraph 状态图

- State Schema 定义（包含所有 Agent 需要的共享状态）
- 节点定义 + 条件边（单步/多步分支、审核阻断、错误处理）
- 流式输出支持

**产出**：`backend/agents/graph.py` + `backend/agents/state.py`

### 6.2 联合分析 Agent

职责（三合一，减少串行 LLM 调用）：
- **Phase 1**：意图完整性检查 → 模糊时生成追问
- **Phase 2**：调用查询值标准化（Phase 4 各模块）
- **Phase 3**：术语翻译 + 复杂度判断（单步/多步）

输出：结构化查询意图 + 标准化值 + 复杂度判定

**产出**：`backend/agents/joint_analysis.py`

### 6.3 计划生成 Agent

- 多步判定：
  ```python
  MULTI_STEP_PATTERNS = [
      ("对比|比较|变化|差异|环比|同比", "需要两个时间窗口对比"),
      ("先.*再|然后|最后|第.*步", "明确的多步骤指令"),
      ("同时查|分别查", "多个独立查询"),
  ]
  ```
- 图谱查找 JOIN 路径
- 子问题依赖排序 → DAG
- 缓存检查（复用已有结果）

**产出**：`backend/agents/plan_generator.py`

### 6.4 执行+审核 Agent

- 正常流程：SQL 生成 → 安全校验 → 审核阻断 → 执行 → 缓存
- 对单步和多步均适用
- 多步时按 DAG 顺序执行，子结果传递

**产出**：`backend/agents/executor_auditor.py`

### 6.5 可配置审核策略

审核触发条件（可配置）：
- 语义来源为 `llm_fallback` → 强制审核
- 查询涉及敏感表 → 审核
- 返回数据量 > 阈值 → 审核
- 查询复杂度（多步/JOIN 数）> 阈值 → 审核

**产出**：`backend/agents/audit_policy.py`

### 6.6 多步查询串联

- DAG 执行器：拓扑排序 → 串行/并行执行
- 子结果传递（前一步结果作为后一步上下文）
- 最终结果合并 + LLM 摘要

**产出**：`backend/pipeline/multi_step.py`

> **检查点**：输入 "对比本月和上月的销售额，按地区排名"，能拆解为多步、生成计划、执行

---

## Phase 7 — 错误自愈系统（3-4 天）

> 文档 §五：错误自愈系统

### 7.1 错误分类器

```python
class ErrorType(Enum):
    TABLE_NOT_FOUND = "table_not_found"       # → 实时刷新表列表
    COLUMN_NOT_FOUND = "column_not_found"     # → 刷新字段列表 + 关联表查找
    SQL_SYNTAX_ERROR = "sql_syntax_error"     # → LLM 重写
    TYPE_MISMATCH = "type_mismatch"           # → 自动添加转换函数
    OTHER = "other"                           # → 告知用户 + 记录日志
```

**产出**：`backend/healing/classifier.py`

### 7.2 元数据过期处理

- 表不存在 → 实时刷新表列表 → 结构相似度匹配 → 自动更正
- 字段不存在 → 刷新字段列表 → 名相似度匹配 → 自动更新
- 变更记录回写元数据存储

**产出**：`backend/healing/metadata_sync.py`

### 7.3 跨表字段自愈

```
missing_column → 向量库全局搜索 → 过滤关联表(candidates)
  → 查图谱找 JOIN 路径 → 找到 → 自动 JOIN 结果
  → 找不到 → 返回候选列表给用户
```

**产出**：`backend/healing/cross_table.py`

### 7.4 SQL 重写修复

- SQL 语法错误 → LLM 重写（附加错误信息）→ 语法校验 → 重试
- 类型不匹配 → LLM 添加 CAST/转换函数 → 重试
- 最大重试次数限制（默认 3 次）

**产出**：`backend/healing/sql_rewrite.py`

### 7.5 错误学习闭环

- `fix_type = metadata_sync` → 更新向量库 + 图谱
- `fix_type = auto_join` → 图 JOINS_WITH 频次 +1、向量库补充关联上下文
- `fix_type = sql_rewrite` → 记录 SQL 错误模式到 PG

**产出**：`backend/healing/learning.py`

> **检查点**：模拟元数据过期场景，系统自动修复并正确返回结果

---

## Phase 8 — 上下文记忆与用户特征（3-4 天）

> 文档 §十一 + §三 3.1 上下文记忆管理

### 8.1 会话管理

- 会话 ID 生成与管理
- Redis 存储短期记忆（最近 N 轮对话，上下文窗口）
- 对话历史构建（给 LLM 用的 context）

**产出**：`backend/memory/session.py`

### 8.2 查询结果缓存

- Redis 缓存，TTL 5 分钟
- 缓存 Key：`query_cache:{normalized_query_hash}`
- 相同标准化查询 → 直接返回缓存结果
- 缓存命中率监控

**产出**：`backend/memory/cache.py`

### 8.3 长期摘要

- 对话结束时异步触发
- LLM 摘要（关键信息：查询了什么、用了哪些表、有什么偏好）
- 存入 PostgreSQL `conversation_summaries` 表

**产出**：`backend/memory/summarizer.py`

### 8.4 用户特征记录 Agent（异步）

维度：
- 技能水平（手动选择 + 行为推断）
- 常用表（查询频率统计）
- 术语习惯（纠正反馈记录）
- 时间偏好（历史查询推断，无时间词时的默认范围）

**产出**：`backend/profile/feature_agent.py`

### 8.5 用户画像存储

- PostgreSQL 数据模型：`user_profiles`、`user_table_preferences`、`user_term_mappings`
- 增量更新（对话结束后异步写入）
- 查询接口（Agent 启动时加载）

**产出**：`backend/profile/store.py`

> **检查点**：多轮对话能记住上下文，用户偏好影响查询结果

---

## Phase 9 — API Gateway + Web Chat UI（5-7 天）

> 文档 §二 2.1 用户交互层

### 9.1 API Gateway（FastAPI）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/query` | POST | 提交查询，返回 SSE 流式 |
| `/api/query/{id}` | GET | 查询历史详情 |
| `/api/query/{id}/confirm` | POST | 审核确认（通过/拒绝/修改） |
| `/api/query/{id}/cancel` | POST | 取消等待审核的查询 |
| `/api/conversations` | GET | 对话列表 |
| `/api/conversations/{id}` | GET | 对话消息列表 |
| `/api/session` | POST | 创建新会话 |

- WebSocket 端点用于流式 Agent 状态推送
- 请求/响应模型定义
- 错误处理与统一响应格式
- CORS 配置

**产出**：`backend/api/`

### 9.2 Next.js 项目初始化

- 项目脚手架（App Router）
- Tailwind CSS 配置
- API 调用层（fetch 封装 + SSE 处理）

**产出**：`frontend/`

### 9.3 聊天界面

- 消息气泡组件（用户消息 / 系统消息 / Agent 思考过程）
- 流式输出（打字机效果）
- 追问交互（选项卡片）
- 输入框（支持多行、发送按钮、停止生成）

### 9.4 结果展示

- 表格组件（数据结果渲染）
- 简单图表（时间序列折线、分类柱状图）
- 自然语言摘要（LLM 生成的解释文字）
- SQL 展示（可折叠，显示生成的 SQL）

### 9.5 审核交互

- 审核卡片（等待审核的查询）
- 确认 / 拒绝 / 修改 SQL 操作
- 审核结果反馈

### 9.6 前后端联调

- 端到端测试场景覆盖
- 错误状态处理（网络异常、超时、服务错误）

> **检查点**：浏览器里能完成对话查询全流程

---

## Phase 10 — 管理端界面（4-5 天）

> 文档 §十二 + §七 Level 3 + §九

### 10.1 元数据同步状态面板

- 最近同步时间 + 状态
- 变更日志列表（表/字段 增删改）
- 手动触发同步按钮
- 同步历史图表

### 10.2 图谱可视化

- Neo4j 可视化嵌入（或使用 vis.js / cytoscape.js）
- Table 节点 + Column 节点 + 关系边
- 确认/拒绝推断外键（Level 3 人工补充）
- 添加同义关系（SAME_MEANING 边）

### 10.3 值映射管理

- 枚举别名 CRUD（按表/字段分组）
- 区域字典管理（树形结构，层级编辑）
- 名称简称管理（搜索 + 批量导入）

### 10.4 热词词典管理

- 术语 → 字段映射 CRUD
- 业务指标公式编辑 + 锁定/解锁
- 批量导入/导出

### 10.5 固定日期周期配置

- 周期名称 + 起始月日 + 结束月日 + 描述
- CRUD 界面

### 10.6 审核策略配置

- 触发条件配置：
  - 语义来源为 llm_fallback 时强制审核
  - 敏感表列表
  - 数据量阈值
  - 复杂度阈值（JOIN 数 / 步数）
- 审核模式：无审核 / 仅高风险 / 全部审核

---

## Phase 11 — 生产加固（3-5 天）

> 文档 §十三 + §十四

### 11.1 监控指标接入

| 指标 | 告警阈值 |
|------|----------|
| 查询延迟 P95 | > 5s |
| 语义匹配未命中率 | > 20% |
| 值标准化未命中率 | > 15% |
| 人工审核占比 | > 50% |
| 错误自愈成功率 | < 80% |
| 元数据同步延迟 | > 2小时 |

- Prometheus metrics 导出
- Grafana Dashboard 模板

### 11.2 审计日志完善

- 全量查询日志（不存原始结果数据）
- 审核操作日志
- 错误日志
- 告警规则配置

### 11.3 初始化脚本

10 步初始化流程自动化：
1. 连接数据源 → 只读账户 + 资源限制
2. 元数据学习（L0-L2，脱机批量）
3. 值映射初始化（枚举发现、区域导入、名称提取）
4. 图谱构建 + 外键推断
5. 向量化存储
6. 热词导入 + 业务指标锁定
7. 启动元数据同步定时任务（每天凌晨）
8. 管理员确认（图谱 + 值映射）
9. 审核策略配置
10. 正式上线

### 11.4 性能优化

- LLM 调用缓存（相同 Prompt + Schema → 缓存结果）
- 向量检索批量化
- 图谱查询优化（预计算常用路径）
- 数据库连接池调优

### 11.5 文档

- 部署文档（Docker Compose 部署步骤）
- 运维手册（日常巡检、故障处理）
- API 文档（自动生成 OpenAPI）
- 管理员手册（值映射配置、审核策略调优）

---

## 关键技术决策回顾

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Agent 编排 | LangGraph，合并澄清+分析+值标准化 | 减少串行 LLM 调用 |
| 语义匹配 | 四层递进（词典→行业→向量→LLM） | 确定性优先、成本可控 |
| 业务指标 | 词典锁定，禁止 LLM 动态编造 | 保证核心业务准确性 |
| 枚举映射 | 确定性规则（别名）+ LLM 兜底 | 不做向量化，避免过度设计 |
| 数值范围 | 追问用户，不自动量化 | 避免业务定义不清导致错误 |
| 多条件逻辑 | 交由 LLM 原生处理 | 不建独立解析器 |
| 错误自愈 | 元数据同步为主 + 运行时修复为兜底 | 表名错误根因是元数据过期 |
| 名称同步 | 查询时 fallback + 异步学习 | V1 不设定时任务 |
| 图谱用途 | 管理端可视化 + Agent JOIN 路径发现 | 双重价值 |
| 元数据学习 | 四层递进，离线批量 | 逐步提升覆盖率，人工兜底 |
| 审核 | 可配置策略，按风险分级 | 安全与效率平衡 |

---

## V1 明确不做

| 项目 | 说明 |
|------|------|
| 多数据源 | V1 仅单数据源 |
| 模糊数值自动量化 | 追问用户 |
| 财年/农历周期 | 引导用户用绝对日期 |
| 独立复合值逻辑解析器 | 交由 LLM 处理 |
| 枚举值向量化 | 用确定性规则 |
| 性能预算控制 | 保留监控埋点 |
| 名称词典定时同步 | 用 fallback 机制 |
