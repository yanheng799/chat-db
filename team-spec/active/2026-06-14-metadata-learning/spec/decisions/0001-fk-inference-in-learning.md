# 值重叠度外键推断归属 Phase 2 learning

我们决定把**值重叠度外键推断**纳入 Phase 2 元数据学习的 V1 范围（作为缺口落成后续 issue），而不是延期或挪到 Phase 3 图谱层，因为它是 learning 层「产出带来源的关系事实」职责的一部分，且生产业务库（尤其 MySQL）普遍不声明外键，缺了它 Phase 3 的 JOIN 路径发现会在大量库上退化。

## Status

accepted

## 背景

设计文档 §七 Level 1 与开发计划 2.2 都把「值重叠度外键推断（跨表字段值重叠率 > 阈值 → 推断潜在外键；结合字段名相似度评分；`source=rule_inference`」列为 Phase 2 L1 的职责。但当前实现只做了 L1 的字段名拆词与数据模式检测，外键推断完全未建，`MetadataForeignKey` 也只存 information_schema 里显式声明的外键，无 `confidence`/`is_inferred`/`source` 字段。

## Considered Options

- **A 纳入 Phase 2 learning（已选）**：约 2.5–3.5 天，复用已有 `query_executor` 与数据源连接；Phase 2 产出带置信度的推断外键，Phase 3 图谱直接消费。符合「learning 产出语义事实、graph 消费」的分层。LLM 零成本（纯 SQL 聚合）。
- **B 明确排除（本期不做）**：0 工作量，但 Phase 3 图谱长期缺 `INFERRED_REF` 边；未声明外键的库（MySQL 常见）JOIN 发现退化，Phase 5 联调时才暴露。隐藏成本高。
- **C 拆到 Phase 3 图谱**：工作量同 A，但图谱层被迫引入「连活库采样」能力，破坏 §七产出 / §九消费 分层，`rule_inference` 这种 learning 溯源被硬挂到图谱边。

## Consequences

- Phase 2 范围增加一个缺口 issue（数据模型扩展 + 候选生成 + 重叠查询 + 评分 + 编排接入），开发计划 Phase 2 预留时间大致覆盖。
- 需一次 Alembic 迁移扩展 `MetadataForeignKey`（或新增推断外键表）——高回退成本，是该决策需要被记录的主因。
- Phase 3 图谱只消费推断外键，不再承担「连活库算重叠」职责，边界保持干净。
- 若该 issue 未能与 Phase 3 同步交付，图谱会在未声明外键的库上暂时只有 DECLARED FK——这是已知短期退化，需在 Phase 3 规格里显式标注。
