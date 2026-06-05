# Agent Harness 文档索引

> 最近更新：2026-06-05
> 更新原因：项目骨架阶段初始建立

## 文档地图

| 文档 | 用途 | 何时阅读 |
|------|------|----------|
| [commands.md](commands.md) | 安装、测试、lint、启动命令 | 执行任何开发任务前 |
| [architecture-map.md](architecture-map.md) | 模块边界、数据流、代码入口 | 修改或新增模块前 |
| [coding-rules.md](coding-rules.md) | 编码约束、禁止事项、TDD 流程 | 编写任何代码前 |
| [verification.md](verification.md) | 按变更类型的验证策略 | 提交代码前 |
| [review-rubric.md](review-rubric.md) | 自查清单、评审关注点 | 完成 issue 实现后 |
| [known-failures.md](known-failures.md) | 已知失败模式与规避方式 | 遇到构建/测试/运行失败时 |
| [harness-debt.md](harness-debt.md) | 阻碍 agent 独立工作的缺口 | 评估项目健康度、排优先级时 |

## 最小必读集合

Agent 执行任何代码任务前，**必须**阅读：

1. `CLAUDE.md`（项目入口）
2. 本文件（文档索引）
3. `commands.md`（确认命令可执行）
4. `coding-rules.md`（确认编码约束）

## 按任务类型的推荐阅读

| 任务类型 | 额外必读 |
|----------|----------|
| 新增模块或包 | `architecture-map.md` |
| 修改现有模块 | `architecture-map.md` + `verification.md` |
| 修复 bug | `known-failures.md` + `verification.md` |
| 重构 | `architecture-map.md` + `coding-rules.md` |
| 添加测试 | `verification.md` + `coding-rules.md`（TDD 部分） |
| 配置变更 | `commands.md`（环境变量部分） |

## 与其他文档的关系

- `CLAUDE.md` 是项目总入口，指向本索引
- `docs/自然语言数据库查询需求设计.md` 是产品需求规格（V5.0），不改代码时不必阅读
- `docs/development-plan.md` 是分阶段实施计划，规划工作范围时阅读
