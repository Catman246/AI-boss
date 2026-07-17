# BOSS View Sync Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the readable local navigation synchronize one managed BOSS tab, while scheduled greetings briefly visit recommended candidates and always restore communication when safe.

**Architecture:** `BossAdapter.open_view()` owns page selection and navigation. `GreetingScheduler.run_once()` restores the chat view after each non-verification attempt. A small authenticated API exposes manual switching, and the existing static UI calls it from readable rail buttons.

**Tech Stack:** Python 3, FastAPI, DrissionPage, vanilla HTML/CSS/JavaScript, unittest.

## Global Constraints

- Do not add a package or runtime network dependency.
- Do not bypass BOSS verification, login controls, quotas, or risk controls.
- Keep one greeting per scheduled execution and preserve human review for messages.
- The workspace `.git` directory is empty, so verification replaces commit steps.

---

### Task 1: Managed BOSS View API

**Files:**
- Modify: `app/boss.py`
- Modify: `app/main.py`
- Test: `tests/test_boss.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `BossAdapter.open_view(view: str) -> dict[str, str]`
- Produces: authenticated `POST /api/boss/view/{view}` for `chat` and `recommend`

- [ ] Add failing tests proving the existing BOSS tab navigates to the requested view and invalid views are rejected.
- [ ] Run `\.venv\Scripts\python.exe -m unittest tests.test_boss tests.test_api -v` and confirm failure.
- [ ] Implement the minimum shared tab selection and API route.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Scheduled Return to Communication

**Files:**
- Modify: `app/greetings.py`
- Test: `tests/test_greetings.py`

**Interfaces:**
- Consumes: `BossAdapter.open_view("chat")`
- Produces: `status()["running"] -> bool`

- [ ] Add failing tests for restore after success, restore after ordinary failure, no restore after verification, and restore failure pausing the plan.
- [ ] Run `\.venv\Scripts\python.exe -m unittest tests.test_greetings -v` and confirm failure.
- [ ] Add a guarded `finally` restoration that never masks the greeting result or original error.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Readable Navigation and Manual Sync

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.css`
- Modify: `app/static/app.js`
- Test: `tests/test_static.py`

**Interfaces:**
- Consumes: `POST /api/boss/view/chat` and `POST /api/boss/view/recommend`
- Produces: visible icon-and-label controls for `会话`, `交接任务`, `主动招呼`, `知识库`, and `退出登录`

- [ ] Add a failing static test for complete labels, Lucide SVG markers, and both view-switch API calls.
- [ ] Run `\.venv\Scripts\python.exe -m unittest tests.test_static -v` and confirm failure.
- [ ] Replace single-character controls, widen the rail, preserve badges, wire manual switching, and expose the scheduler running message.
- [ ] Run static tests and `node --check app\static\app.js`.

### Task 4: End-to-End Verification

**Files:**
- Verify only; no production edits expected.

- [ ] Run `\.venv\Scripts\python.exe -m unittest discover -s tests -v` and expect all tests to pass.
- [ ] Run `\.venv\Scripts\python.exe -m py_compile app\boss.py app\greetings.py app\main.py` and expect exit code 0.
- [ ] Restart only the verified Uvicorn listener on port `8765`.
- [ ] Confirm `/`, login, greeting status, and manual view validation without executing a greeting.
