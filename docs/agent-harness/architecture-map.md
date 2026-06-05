# 架构地图

> 本文档只记录 agent 执行任务时需要理解的架构信息，不复制完整设计文档。
> 完整设计见 `docs/自然语言数据库查询需求设计.md`（V5.0 规格）。

## 包结构总览

```
src/
  config/       # 配置管理（pydantic-settings，读取 .env）
  llm/          # LLM 调用抽象层（chat/stream/embed 统一接口）
  db/           # 数据库连接层（SQLAlchemy async，强制只读）
  metadata/     # 元数据提取与同步（information_schema → PG）
  learning/     # 元数据学习（L0 提取 → L1 规则 → L2 LLM 推断）
  knowledge/    # 知识库（Milvus 向量 + Neo4j 图 + 热词 + 值映射）
  normalizer/   # 查询值标准化（时间/枚举/区域/名称/量词）
  semantic/     # 四层语义匹配（热词→行业→向量→LLM 兜底）
  sql/          # SQL 生成 + 安全校验 + 执行
  pipeline/     # 单步/多步查询串联
  agents/       # LangGraph 多 Agent 编排（联合分析/计划生成/执行审核）
  healing/      # 错误自愈（分类/元数据同步/跨表/SQL 重写/学习闭环）
  memory/       # 会话管理 + 查询缓存 + 长期摘要
  profile/      # 用户特征记录与存储
  api/          # FastAPI Gateway（REST + SSE）
  utils/        # 通用工具函数
```

## 核心数据流

查询生命周期（从用户输入到结果返回）：

```
用户输入（中文自然语言）
  │
  ▼
agents/joint_analysis          ← 三合一：意图检查 + 值标准化 + 术语翻译
  │
  ├─ normalizer/*              ← 时间/枚举/区域/名称/量词 标准化
  ├─ semantic/matcher          ← 4 层递进匹配
  │
  ▼
单步 ──────────────────┐
  │                    │
多步 → agents/plan_generator  ← DAG 规划，图谱 JOIN 路径
       │              │
       ▼              ▼
agents/executor_auditor       ← SQL 生成 → 安全校验 → 审核门 → 执行 → 缓存
  │
  ├─ sql/generator + sql/security
  │
  ├─ 失败 → healing/*         ← 错误分类 → 自愈 → 学习反馈
  │
  ▼
结果返回
```

## 知识层（离线构建）

```
metadata/ + learning/          ← 提取 schema (L0) → 推断语义 (L1/L2)
  │
  ▼
knowledge/
  ├── Milvus 向量              ← 字段语义描述、查询样例
  ├── Neo4j 图                 ← 表关系、外键、JOIN 路径、同义字段
  ├── 热词词典                 ← 术语→字段映射，锁定业务指标
  └── 值映射中心               ← 枚举别名、区域字典、名称简称
```

## 运行时数据存储

```
memory/                        ← Redis 短期记忆（最近 N 轮对话）
  ├── session 会话管理
  ├── cache  查询缓存 (TTL 5min)
  └── summarizer 长期摘要 → PostgreSQL
profile/                       ← 用户画像 → PostgreSQL
```

## 关键模块依赖关系

```
config ──→ 所有模块（全局配置）
llm ──→ learning, semantic, sql, agents, memory, healing, profile（LLM 调用）
db ──→ metadata, sql, memory, profile（数据库连接）
knowledge ──→ semantic, normalizer, healing, agents（知识查询）
normalizer ──→ agents/joint_analysis（值标准化）
semantic ──→ agents/joint_analysis（语义匹配）
sql ──→ agents/executor_auditor（SQL 生成与执行）
healing ──→ agents/executor_auditor（错误自愈）
```

## Agent 最容易误判的点

1. **`normalizer/` 和 `semantic/` 是两个独立子系统**：normalizer 标准化查询值（时间→日期、简称→全称），semantic 匹配术语到数据库字段。两者被 `agents/joint_analysis` 分别调用，不应混淆。

2. **`knowledge/` 包含四种不同存储**：Milvus（向量）、Neo4j（图）、热词词典（PG/字典）、值映射（PG）。它们的读写接口完全不同。

3. **`sql/` 包含三个独立职责**：generator（生成 SQL）、security（黑/白名单校验）、executor（只读执行）。security 检查应在 executor 执行前完成。

4. **`agents/` 是编排层，不包含业务逻辑**：具体逻辑在 normalizer、semantic、sql、healing 等模块中。agents 只做流程编排。

5. **`learning/` 是离线流程**：在系统初始化时运行，不在用户查询时运行。用户查询时使用的是 learning 已经产出的知识。

6. **设计文档中的路径与实际不一致**：`docs/development-plan.md` 使用 `backend/` 前缀（如 `backend/db/connection.py`），但实际代码在 `src/` 下（如 `src/db/connection.py`）。**以实际 `src/` 路径为准。**

## 当前状态（骨架阶段）

所有 16 个包仅有空的 `__init__.py`，无实现代码。实现顺序遵循开发计划的 Phase 0 → 11。
