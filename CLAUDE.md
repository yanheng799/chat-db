# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chat-DB is a natural language database query agent system. Users query databases via conversational input in plain Chinese (including industry jargon). The system understands intent, standardizes query values, plans query steps, generates read-only SQL, and supports configurable human review. Built with multi-agent orchestration (LangGraph).

## Commands

```bash
# Install dependencies (use system Python's uv, not venv's)
python -m uv sync --extra dev --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Run tests
.venv/Scripts/python.exe -m pytest                    # all tests
.venv/Scripts/python.exe -m pytest test/test_config/  # single module
.venv/Scripts/python.exe -m pytest test/test_config/test_settings.py::test_x  # single test

# Lint & format
.venv/Scripts/ruff.exe check src/
.venv/Scripts/ruff.exe format src/

# Run API server
.venv/Scripts/python.exe -m uvicorn api.main:app --reload
```

**Note**: `uv` is installed via system Python (`D:/Python/Python311/python.exe -m uv`), not in the venv. Network to PyPI is unreliable — always use `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`.

## Architecture

### Source layout (`src/`)

Flat package structure — `src/` contains business packages directly, no intermediate namespace. Each package maps to a subsystem in the design doc (`docs/自然语言数据库查询需求设计.md`).

**Data flow (query lifecycle):**
```
User Input
  → agents/joint_analysis    (intent check + value normalization + term translation)
  → normalizer/*             (time/enum/region/name/quantifier standardization)
  → semantic/matcher         (4-layer: hot-words → industry → vector → LLM fallback)
  → agents/plan_generator    (multi-step DAG planning, graph-based JOIN path)
  → sql/generator + security (SQL gen, blacklist/whitelist validation)
  → agents/executor_auditor  (audit gate → execute → cache)
  → healing/*                (error self-healing on failure)
```

**Knowledge layer (populated offline):**
- `metadata/` + `learning/` — extract schema (L0), infer semantics (L1 rules, L2 LLM)
- `knowledge/` — Milvus vectors, Neo4j graph (JOIN paths, foreign keys), hot-word dict, value mappings
- `memory/` — Redis session cache, conversation summaries
- `profile/` — async user feature tracking

### Test layout (`test/`)

Mirrors `src/` structure: `test/test_sql/test_security.py` tests `src/sql/security.py`.

### Configuration

All config via `.env` (pydantic-settings). No YAML config file. `.env.example` is the template — copy to `.env` and fill values. `.env` is gitignored.

### Key dependencies

- **Agent orchestration**: langgraph (latest)
- **LLM calls**: langchain + langchain-openai (Qwen3 via DashScope OpenAI-compatible API)
- **Embeddings**: bge-large-zh-v1.5 via local endpoint (port 8001)
- **Vector store**: pymilvus >= 2.6
- **Graph DB**: neo4j (bolt://127.0.0.1:7687)
- **DB**: sqlalchemy >= 2.0 async (asyncpg driver)
- **Web**: fastapi + uvicorn + sse-starlette

### Build system

Hatchling with explicit package list in `[tool.hatch.build.targets.wheel].packages`. When adding a new package under `src/`, it must be added to this list in `pyproject.toml`.

## Design Documents

- `docs/自然语言数据库查询需求设计.md` — V5.0 final spec (system architecture, agent flow, all subsystems)
- `docs/development-plan.md` — phased implementation plan (12 phases, dependency graph)
