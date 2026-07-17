# AI Draft and RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Kimi-generated, RAG-grounded recruitment drafts that always require human review before the existing BOSS send action.

**Architecture:** Keep the existing FastAPI, DrissionPage, SQLite-free frontend structure. Add one SQLite knowledge store and one Kimi draft service; expose narrow APIs and render drafts above the existing composer.

**Tech Stack:** Python 3.13, FastAPI, SQLite, OpenAI Python SDK, vanilla JavaScript and CSS.

## Global Constraints

- Never send AI output automatically.
- Never expose a Kimi key in browser responses, logs, source, tests, or shell output.
- Never auto-switch BOSS contacts or bypass verification/rate limits.
- Drafts target 15-60 Chinese characters and at most two sentences.
- Existing manual chat remains usable when AI or RAG fails.

---

### Task 1: Secure Kimi configuration

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `scripts/configure_kimi.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `C:\Users\81591\Desktop\kimi-keys.txt`
- Produces: `.env` containing `MOONSHOT_API_KEY`, `KIMI_BASE_URL`, and `KIMI_MODEL`

- [ ] Add `.env` and generated SQLite files to `.gitignore`; add placeholder variable names to `.env.example`.
- [ ] Implement a script that extracts candidate `sk-...` values, calls `GET /models`, selects `kimi-k2.6` when available, sends one non-thinking short completion, and atomically writes only the first working key to `.env`.
- [ ] Ensure script output contains only key ordinal, status, selected model, and error category.
- [ ] Add `openai>=1.0` to requirements.
- [ ] Run the script against the supplied key file and verify `.env` exists without displaying its contents.

### Task 2: Local recruitment knowledge store

**Files:**
- Create: `app/knowledge.py`
- Create: `data/recruitment-talk-script-seed.md`
- Create: `tests/test_knowledge.py`

**Interfaces:**
- Produces: `KnowledgeStore.list_entries()`, `create_entry()`, `update_entry()`, `delete_entry()`, and `search(query, limit=4)`

- [ ] Write failing tests for idempotent 30-item seed import, enabled-only retrieval, title/keyword weighting, low-confidence results, and CRUD.
- [ ] Run `D:\python\python.exe -m unittest tests.test_knowledge -v` and confirm failure.
- [ ] Implement the minimum SQLite schema and deterministic Chinese character-bigram scorer.
- [ ] Add the AIHR seed markdown and safety escalation entries without overwriting user edits.
- [ ] Re-run the knowledge tests and confirm pass.

### Task 3: Kimi draft generation and style guard

**Files:**
- Create: `app/ai.py`
- Create: `tests/test_ai.py`

**Interfaces:**
- Consumes: recent messages, job name, retrieved knowledge entries
- Produces: `DraftResult(text, status, sources, fingerprint)`

- [ ] Write failing tests for prompt grounding, duplicate fingerprint stability, short natural output acceptance, verbose/Markdown/placeholder rejection, one rewrite, and low-confidence handoff.
- [ ] Run `D:\python\python.exe -m unittest tests.test_ai -v` and confirm failure.
- [ ] Implement `.env` loading, Kimi non-thinking completion, prompt construction, local quality checks, and one corrective rewrite.
- [ ] Re-run AI tests with a fake client and confirm no real API use.

### Task 4: Authenticated knowledge and draft APIs

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Produces: `GET/POST/PATCH/DELETE /api/knowledge`, `POST /api/contacts/{key}/draft`, and `GET /api/ai/status`

- [ ] Write failing API tests for authentication, knowledge validation, latest-contact-message requirement, source metadata, and proof that draft generation never calls `boss.send`.
- [ ] Run the focused API tests and confirm failure.
- [ ] Initialize the store and draft service in `create_app`, while allowing fakes to be injected.
- [ ] Add validated API routes; return AI failures as draft states without breaking chat routes.
- [ ] Re-run API tests and confirm pass.

### Task 5: Human-review draft interface

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/app.css`
- Modify: `tests/test_static.py`

**Interfaces:**
- Consumes: draft and knowledge APIs
- Produces: visible draft review panel and knowledge management drawer

- [ ] Write failing static checks for AI draft status, sources, adopt/regenerate/ignore buttons, and knowledge controls.
- [ ] Add a compact draft panel above the composer; adopting only copies text to the textarea.
- [ ] Generate once when the latest message fingerprint changes and its sender is `contact`; clear stale drafts on contact changes.
- [ ] Add a simple knowledge drawer for list/create/edit/enable/delete without adding a frontend framework.
- [ ] Run JavaScript syntax and static tests.

### Task 6: End-to-end verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Produces: documented startup, Kimi setup, RAG workflow, and safety boundary

- [ ] Run `D:\python\python.exe -m unittest discover -s tests -v`.
- [ ] Run `node --check app\static\app.js`.
- [ ] Start the local server and verify login, contacts, a generated draft, adoption/editing, and knowledge CRUD in the browser.
- [ ] Confirm no automated BOSS message is sent and no secret appears in responses or logs.
- [ ] Update README with exact setup and failure recovery steps.
