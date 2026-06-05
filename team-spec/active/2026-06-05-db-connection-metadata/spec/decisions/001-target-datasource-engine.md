---
decision_id: P-001
title: 目标数据源引擎选择与连接模型
date: 2026-06-05
status: confirmed
impact_scope: multi-requirement
---

## 决策

V1 同时支持 PostgreSQL 和 MySQL 作为目标数据源引擎。数据源配置通过前端管理界面动态管理，存储在应用数据库中。Phase 1 即使用数据库存储配置（而非 .env 文件）。

## 备选方案

1. 仅支持 PostgreSQL → 简化实现，但限制了用户场景
2. 仅支持 MySQL → 同上
3. V1 就支持运行时多数据源切换 → 过度复杂
4. **V1 部署时选择一种引擎，固定连接**（部分选择）→ 覆盖主流场景
5. **数据源配置存数据库，前端管理**（已确认）→ 从一开始就支持动态配置

## 理由

- 企业用户同时使用 PG 和 MySQL 很常见，V1 不支持任一种都会排除部分场景
- SQLAlchemy 已提供引擎抽象，支持两种引擎的额外成本较低
- 数据源配置属于运行时管理数据，通过数据库存储 + API 管理是更自然的设计
- 从 Phase 1 就用数据库存储，避免后续从 .env 迁移到数据库的转换成本

## 影响

- Phase 1 范围扩大：需要数据源配置模型 + CRUD API（不含前端 UI）
- 连接层从数据库读取配置创建引擎，不从 .env 读取目标数据源信息
- `.env` 仅保留应用自身基础设施配置（应用 PG、Redis、Neo4j 等），目标数据源连接信息不入 .env
- 元数据提取器需要适配 PG 和 MySQL 的 `information_schema` 差异
- 连接层通过 SQLAlchemy dialect 抽象，上层代码不感知引擎差异
- `max_execution_time`（MySQL）和 `statement_timeout`（PG）需要按引擎分别设置
