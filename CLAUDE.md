# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chat-DB is a natural language database query agent system. Users query databases via conversational input in plain Chinese (including industry jargon). The system understands intent, standardizes query values, plans query steps, generates read-only SQL, and supports configurable human review. Built with multi-agent orchestration (LangGraph).

**Tech stack**: Python ≥ 3.11 · LangGraph · LangChain + Qwen3 (DashScope) · Milvus · Neo4j · Redis · PostgreSQL · FastAPI · SQLAlchemy 2.0 async

## Quick Commands

```bash
# Install dependencies (use system Python's uv, not venv's)
python -m uv sync --extra dev --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Run tests
.venv/Scripts/python.exe -m pytest                    # all tests
.venv/Scripts/python.exe -m pytest test/test_config/  # single module
.venv/Scripts/python.exe -m pytest test/test_config/test_settings.py::test_x  # single test

# Lint & format
.venv/Scripts/ruff.exe check --fix src/ && .venv/Scripts/ruff.exe format src/

# Run API server
.venv/Scripts/python.exe -m uvicorn api.main:app --reload
```

**Note**: `uv` is installed via system Python (`D:/Python/Python311/python.exe -m uv`), not in the venv. Network to PyPI is unreliable — always use `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`.

## Source Layout

Flat package structure — `src/` contains 16 business packages directly, no intermediate namespace. Each maps to a subsystem in the design doc.

**Test layout mirrors src/**: `test/test_sql/test_security.py` tests `src/sql/security.py`.

**Configuration**: All via `.env` (pydantic-settings). No YAML config. Copy `.env.example` to `.env`.

**Build system**: Hatchling. New packages under `src/` must be added to `[tool.hatch.build.targets.wheel].packages` in `pyproject.toml`.

## Agent Harness Documentation

详细命令说明、架构地图、编码规则、验证策略、评审清单和已知失败模式都在 harness 文档中：

→ **[docs/agent-harness/index.md](docs/agent-harness/index.md)** — harness 文档总入口

| 文档 | 内容 |
|------|------|
| [commands.md](docs/agent-harness/commands.md) | 所有开发命令、适用场景、常见失败 |
| [architecture-map.md](docs/agent-harness/architecture-map.md) | 模块边界、数据流、依赖关系 |
| [coding-rules.md](docs/agent-harness/coding-rules.md) | OCP/DIP/SRP、禁止事项、TDD 工作流 |
| [verification.md](docs/agent-harness/verification.md) | 按变更类型的验证策略 |
| [review-rubric.md](docs/agent-harness/review-rubric.md) | 实现完成前的自查清单 |
| [known-failures.md](docs/agent-harness/known-failures.md) | 已知失败模式与规避方式 |
| [harness-debt.md](docs/agent-harness/harness-debt.md) | 阻碍 agent 独立工作的缺口 |

## Design Documents

- `docs/自然语言数据库查询需求设计.md` — V5.0 final spec (system architecture, agent flow, all subsystems)
- `docs/development-plan.md` — phased implementation plan (12 phases, dependency graph)
- **注意**：开发计划中使用 `backend/` 路径前缀，实际代码在 `src/` 下，以实际路径为准
