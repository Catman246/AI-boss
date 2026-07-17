# BOSS Conversation Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let the user delete a BOSS conversation from the local contact list while preserving the shared candidate profile and all local history.

**Architecture:** Reuse the existing `boss_key` and `BossAdapter` lock. The browser adapter hovers the matching `.geek-item`, opens its visible menu, clicks delete, confirms only when BOSS asks, and verifies the contact disappeared. The API clears the local `boss_key` only after that verification succeeds.

**Tech Stack:** Python, FastAPI, DrissionPage, SQLite, vanilla JavaScript/CSS.

## Global Constraints

- No new dependency.
- Never delete the local candidate, messages, notes, WeChat identity, interviews, or tasks.
- Require an explicit confirmation in our UI before calling BOSS.
- If BOSS deletion is unknown or fails, keep local data unchanged and do not retry automatically.

---

### Task 1: Browser and local data boundary

**Files:** `tests/test_boss.py`, `tests/test_recruiting.py`, `app/boss.py`, `app/recruiting.py`

- [ ] Add failing tests for `BossAdapter.delete_contact(key)` and `RecruitingStore.detach_boss_contact(candidate_id)`.
- [ ] Verify the tests fail.
- [ ] Implement the minimum browser flow: validate key, locate contact, hover, click the visible delete action, handle a visible confirmation if present, and wait until the keyed contact disappears.
- [ ] Clear only `candidates.boss_key` after external success.
- [ ] Run the focused tests.

### Task 2: Authenticated API

**Files:** `tests/test_api.py`, `app/main.py`

- [ ] Add a failing test for `DELETE /api/candidates/{candidate_id}/boss-conversation`.
- [ ] Assert BOSS deletion happens before local detach and failures leave the candidate linked.
- [ ] Implement the endpoint using the existing session dependency and `BossError` handler.
- [ ] Run the focused API tests.

### Task 3: Hover menu and verification

**Files:** `tests/test_static.py`, `app/static/app.js`, `app/static/app.css`, `app/static/index.html`

- [ ] Add a failing static check for a hover-only ellipsis action and confirmation copy.
- [ ] Render a separate ellipsis button on BOSS contact rows; stop propagation so it does not switch conversations.
- [ ] Show a small menu with Delete; confirm the exact candidate name; disable the action while deleting.
- [ ] On success clear selection when needed, reload the list, and show a toast; on failure keep the row and show the error.
- [ ] Bump the static asset version, run all tests, rebuild the desktop app, and verify the installed UI without deleting a real conversation.
