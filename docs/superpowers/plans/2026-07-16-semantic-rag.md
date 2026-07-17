# Semantic RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local Chinese semantic retrieval without making the application depend on an external vector service.

**Architecture:** Keep SQLite for knowledge CRUD and add a lazy FastEmbed/LanceDB index as derived local data. Fuse semantic similarity with the existing lexical score and fall back to lexical retrieval when the optional backend is unavailable.

**Tech Stack:** Python 3.13, FastEmbed, `BAAI/bge-small-zh-v1.5`, LanceDB, unittest

## Global Constraints

- Install dependencies only in the project `.venv`.
- Keep `.venv`, `star`, model files, and vector data out of Git.
- Do not deploy Chatwoot, Rasa, Qdrant, or another service.
- Preserve the existing public `KnowledgeStore` API.

---

### Task 1: Local environment and ignored artifacts

**Files:**
- Modify: `.gitignore`
- Modify: `requirements.txt`
- Modify: `run.ps1`

**Interfaces:**
- Produces: a project-local Python runtime with `fastembed` and `lancedb`.

- [ ] Add `.venv/`, `star/`, `data/models/`, and `data/lancedb/` to `.gitignore`.
- [ ] Pin compatible FastEmbed and LanceDB versions in `requirements.txt`.
- [ ] Make `run.ps1` prefer `.venv/Scripts/python.exe` and fail with an installation instruction if missing.
- [ ] Create `.venv` and install `requirements.txt`.

### Task 2: Semantic retrieval contract

**Files:**
- Modify: `tests/test_knowledge.py`
- Modify: `app/knowledge.py`

**Interfaces:**
- Consumes: `KnowledgeStore(path: Path)` and existing CRUD methods.
- Produces: `KnowledgeStore.search(query, limit=4, minimum_score=0.18)` with hybrid retrieval.

- [ ] Write a failing test where `还有招人吗` semantically matches an entry phrased as `岗位目前开放招聘` despite no useful bigram overlap.
- [ ] Write a failing test proving an unavailable semantic backend falls back to lexical search.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Add the minimum lazy embedding/index implementation and score fusion.
- [ ] Run the focused tests and the complete test suite.

### Task 3: Model download and end-to-end smoke test

**Files:**
- Create: `scripts/setup_semantic_search.py`
- Modify: `README.md`

**Interfaces:**
- Produces: locally cached BGE model and a semantic search smoke result.

- [ ] Add a setup script that downloads the configured model into `data/models/fastembed` and verifies one embedding.
- [ ] Run the script, then verify paraphrase retrieval against a temporary knowledge database.
- [ ] Document local setup, clone setup, cache paths, and the fact that generated artifacts are not committed.
- [ ] Run all tests and syntax checks.
