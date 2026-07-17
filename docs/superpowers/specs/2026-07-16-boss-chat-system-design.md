# BOSS Chat Local System Design

## Goal

Build a local, single-user web system that lets the account owner read BOSS
contacts and conversations and send text messages through the already logged-in
BOSS website.

The first version supports one computer, one BOSS account, and one system login:

- Username: `admin`
- Password: `123456`

## Scope

Included:

- Local system login and logout
- BOSS browser connection status
- Automatic launch or reuse of the Chrome profile on debug port `9333`
- Contact list and unread indicators available in the current BOSS page
- Conversation history for the selected contact
- Sending one text message to one explicitly selected contact
- Delivery/read status when exposed by the page
- Clear errors for expired login, CAPTCHA, disconnected browser, or changed page

Excluded from the first version:

- Bulk messaging
- Automatic replies
- Scheduled messages
- Candidate scoring or resume management
- Multiple users, accounts, or remote deployment
- CAPTCHA or platform-control bypasses

## Architecture

Use the packages already installed in `D:\python`:

- FastAPI and Uvicorn for the local HTTP service
- DrissionPage for BOSS browser control
- Plain HTML, CSS, and JavaScript for the interface

The server binds only to `127.0.0.1`. No database is required in the first
version; BOSS remains the source of contacts, messages, and delivery state.

```text
Browser UI -> FastAPI -> serialized BOSS adapter -> DrissionPage -> Chrome 9333
```

The BOSS adapter owns one browser connection and one lock. Every read or write
operation runs through this adapter so two requests cannot manipulate different
contacts at the same time.

Chrome uses the existing persistent profile:

`C:\Users\81591\AppData\Local\DrissionPage\Chrome9333`

If Chrome is running, the adapter connects to it. If it is closed, the adapter
starts Chrome with the same profile and port, preserving login state when BOSS
has not expired the session.

## Backend Interface

- `POST /api/login`: validate `admin / 123456` and create a local session
- `POST /api/logout`: clear the session
- `GET /api/status`: return system and BOSS connection/login state
- `GET /api/contacts`: return contact keys, names, previews, times, and unread state
- `GET /api/contacts/{key}/messages`: select and read one conversation
- `POST /api/contacts/{key}/messages`: send one non-empty text message

Each send operation must:

1. Select the contact using an opaque key extracted from the page.
2. Verify the active chat header matches the expected contact.
3. Verify the editor is empty before inserting text.
4. Click the visible send button once.
5. Read the resulting message and delivery state from the page.

If any verification fails, the backend returns an error and does not send.

## Authentication

Credentials are checked only by the backend and are never embedded in frontend
JavaScript. A random in-memory session token is stored in an `HttpOnly`,
`SameSite=Strict` cookie. Restarting the server logs the local system user out.

This is suitable only for loopback access. Remote or multi-user deployment will
require configurable password hashing, HTTPS, persistent sessions, and CSRF
protection.

## Interface

The desktop interface has three stable areas:

- Narrow navigation rail with connection state and logout
- Contact list with search, unread marker, preview, and refresh
- Conversation area with candidate name, message history, delivery state, and a
  text composer

The UI performs a passive DOM read every five seconds while the local app is
visible. Passive reads may inspect the current conversation and contact-list
unread markers, but they must not navigate, click, or change the active BOSS
conversation. Selecting a contact remains an explicit user action. Enter sends
and Shift+Enter inserts a newline.

## Failure Handling

- Browser closed: reconnect or launch with the persistent profile
- BOSS logged out: show "需要登录 BOSS" and stop message operations
- CAPTCHA/security verification: show an action-required banner and wait for the
  user to finish it in Chrome; never navigate away from the verification page
- DOM selector changed: return a structured adapter error instead of guessing
- Duplicate or stale contact: fail active-header verification and do not send
- Send timeout: refresh the conversation and report an unknown result without
  retrying automatically, preventing duplicate messages

## Verification

- Unit-level API checks use a fake adapter for login, contact reads, and the
  single-send guard.
- A local smoke test connects to port `9333`, reads contacts, opens one existing
  conversation, and confirms the composer is available.
- Sending during verification requires an explicit user-selected recipient and
  message; tests never send automatically.
