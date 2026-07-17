# BOSS Chat Local System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local authenticated web chat interface that reads and sends BOSS messages through the persistent DrissionPage Chrome session.

**Architecture:** FastAPI serves a static desktop UI and a small JSON API. A single locked `BossAdapter` owns all DrissionPage access, validates the active recipient before sending, and never retries a send automatically.

**Tech Stack:** Python 3, FastAPI, Uvicorn, DrissionPage, pytest, HTML, CSS, JavaScript

## Global Constraints

- Bind only to `127.0.0.1`.
- Support one local user and one BOSS account.
- System credentials are `admin / 123456`.
- Use Chrome port `9333` and profile `C:\Users\81591\AppData\Local\DrissionPage\Chrome9333`.
- Do not implement bulk sends, automatic replies, CAPTCHA bypasses, or private BOSS API calls.
- Never retry an uncertain send.

---

### Task 1: Application API and Authentication

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: an object stored at `app.state.boss` with `status()`, `contacts()`, `messages(key)`, and `send(key, text)` methods.
- Produces: `create_app(boss=None) -> FastAPI` and authenticated `/api` routes.

- [ ] Write API tests for login rejection, login success, protected routes, empty-message rejection, and adapter delegation.
- [ ] Run `D:\python\python.exe -m pytest tests\test_api.py -q` and verify failure because `app.main` does not exist.
- [ ] Implement a random HttpOnly session cookie, constant-time credential comparison, request validation, structured errors, and static-file serving.
- [ ] Run the API tests and verify all pass.

### Task 2: Serialized DrissionPage Adapter

**Files:**
- Create: `app/boss.py`
- Test: `tests/test_boss.py`

**Interfaces:**
- Produces: `BossAdapter.status()`, `BossAdapter.contacts()`, `BossAdapter.messages(key)`, and `BossAdapter.send(key, text)`.
- Contact dictionaries contain `key`, `name`, `job`, `time`, `preview`, and `unread`.
- Message dictionaries contain `sender`, `text`, `time`, and `status`.

- [ ] Write pure parser tests using representative contact and message HTML fragments.
- [ ] Run `D:\python\python.exe -m pytest tests\test_boss.py -q` and verify failure because the parser does not exist.
- [ ] Implement pure HTML parsing helpers, browser startup/reuse, BOSS-login detection, contact selection by `data-id`, active-header verification, and guarded one-click sending.
- [ ] Run the adapter tests and verify all pass.

### Task 3: Desktop Chat Interface

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/app.css`
- Create: `app/static/app.js`

**Interfaces:**
- Consumes: the JSON endpoints from Task 1.
- Produces: login, connection status, contact list, conversation view, composer, delivery state, and logout.

- [ ] Build one accessible document with a login view and application view.
- [ ] Add a restrained teal/charcoal interface with stable desktop dimensions, contact search, loading/empty/error states, and no nested cards.
- [ ] Implement five-second passive DOM reads that never navigate or click, with sends triggered solely by the send button or Enter; Shift+Enter inserts a newline.
- [ ] Verify long names/messages wrap and controls do not shift layout at 1440x900 and 1920x1080.

### Task 4: Run and End-to-End Verification

**Files:**
- Create: `run.ps1`
- Create: `README.md`
- Create: `requirements.txt`

**Interfaces:**
- Produces: one-command local startup at `http://127.0.0.1:8765`.

- [ ] Add the startup script and concise operating instructions.
- [ ] Run `D:\python\python.exe -m pytest -q` and verify all tests pass.
- [ ] Start the service and verify `/api/status` rejects unauthenticated access.
- [ ] Log in through the UI, confirm the live BOSS status and contact list, open one conversation, and verify the composer is available without sending.
- [ ] Capture a desktop screenshot and inspect it for clipping, overlaps, blank states, and console errors.
