# Readable Navigation Design

## Goal

Replace ambiguous single-character rail controls with readable navigation labels while preserving the current desktop workflow.

## Design

- Widen the left navigation rail only as much as needed for icon-and-label controls.
- Use inline Lucide icons so the local application has no new package or network dependency.
- Label the entries: `会话`, `交接任务`, `主动招呼`, `知识库`, and `退出登录`.
- Keep the current active state, task and greeting badges, BOSS connection indicator, keyboard focus styles, and button behavior.
- Do not change application routing, APIs, drawer behavior, or mobile layout.

## BOSS View Synchronization

- Use the existing logged-in BOSS tab instead of opening a second account session.
- Clicking `会话` navigates the managed BOSS tab to the communication page before refreshing contacts and messages.
- Clicking `主动招呼` navigates the managed BOSS tab to the recommended-candidates page and opens the local plan drawer.
- Every scheduled run switches to recommended candidates, greets exactly one candidate, and returns to communication automatically.
- A verification page is never navigated away from automatically; verification pauses the plan for manual handling.
- Ordinary failures still attempt to restore communication, while a restore failure pauses the plan without retrying the greeting.
- The local application stays on its current screen during scheduled switching and exposes the running state in the greeting drawer.

## Verification

- Existing static and API tests continue to pass.
- Every navigation button has matching visible text, `title`, and `aria-label`.
- Labels and badges fit without overlap at the supported desktop viewport.
- Adapter tests prove one existing BOSS tab is reused for both views.
- Scheduler tests prove communication is restored after success and ordinary failure, but not after verification.
