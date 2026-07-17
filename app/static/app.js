const state = {
  channel: "boss",
  candidates: [],
  selectedId: null,
  selected: null,
  messages: [],
  connected: false,
  loggedIn: false,
  aiConfigured: false,
  semanticReady: false,
  sending: false,
  polling: false,
  pollCount: 0,
  messageMode: "reply",
  draft: null,
  draftSignature: null,
  ignoredDrafts: new Set(),
  tasks: [],
  knowledge: [],
  greetings: null,
  greetingLogs: [],
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  loginView: $("#login-view"), appView: $("#app-view"), loginForm: $("#login-form"), loginError: $("#login-error"),
  username: $("#username"), password: $("#password"), conversationButton: $("#conversation-button"), logoutButton: $("#logout-button"), refreshButton: $("#refresh-button"),
  bossTab: $("#agent-boss"), wechatTab: $("#agent-wechat"), search: $("#contact-search"), contactList: $("#contact-list"),
  contactCount: $("#contact-count"), channelCaption: $("#channel-caption"), newCandidateButton: $("#new-candidate-button"),
  railStatus: $("#rail-status"), statusBanner: $("#status-banner"), emptyConversation: $("#empty-conversation"),
  conversationView: $("#conversation-view"), activeAvatar: $("#active-avatar"), activeName: $("#active-name"), activeJob: $("#active-job"),
  activeStage: $("#active-stage"), connectionChip: $("#connection-chip"), aiChip: $("#ai-chip"), semanticChip: $("#semantic-chip"),
  messageList: $("#message-list"), messageInput: $("#message-input"), sendButton: $("#send-button"), sendFeedback: $("#send-feedback"),
  composerRecipient: $("#composer-recipient"), messageMode: $("#message-mode"), modeReply: $("#mode-reply"), modeIncoming: $("#mode-incoming"),
  draftPanel: $("#ai-draft-panel"), draftStatus: $("#ai-draft-status"), draftText: $("#ai-draft-text"), draftSources: $("#ai-draft-sources"),
  adoptDraft: $("#adopt-draft"), regenerateDraft: $("#regenerate-draft"), ignoreDraft: $("#ignore-draft"),
  contextEmpty: $("#context-empty"), contextContent: $("#context-content"), candidateId: $("#candidate-id"), candidateForm: $("#candidate-form"),
  candidateStage: $("#candidate-stage"), candidateName: $("#candidate-name"), candidateJob: $("#candidate-job"), wechatId: $("#wechat-id"),
  privateContact: $("#private-contact"), candidateTags: $("#candidate-tags"), candidateNotes: $("#candidate-notes"), interviewForm: $("#interview-form"),
  interviewTime: $("#interview-time"), interviewLocation: $("#interview-location"), taskButton: $("#task-button"), taskBadge: $("#task-badge"),
  taskDrawer: $("#task-drawer"), taskClose: $("#task-close"), taskList: $("#task-list"), drawerBackdrop: $("#drawer-backdrop"),
  greetingButton: $("#greeting-button"), greetingBadge: $("#greeting-badge"), greetingDrawer: $("#greeting-drawer"), greetingClose: $("#greeting-close"),
  greetingPlanList: $("#greeting-plan-list"), greetingPlanCount: $("#greeting-plan-count"), greetingNewPlan: $("#greeting-new-plan"),
  greetingForm: $("#greeting-form"), greetingFormHeading: $("#greeting-form-heading"), greetingPlanId: $("#greeting-plan-id"), greetingPlanName: $("#greeting-plan-name"), greetingEnabled: $("#greeting-enabled"), greetingDailyLimit: $("#greeting-daily-limit"),
  greetingHourlyLimit: $("#greeting-hourly-limit"), greetingStartAt: $("#greeting-start-at"), greetingEndAt: $("#greeting-end-at"),
  greetingToday: $("#greeting-today"), greetingHour: $("#greeting-hour"), greetingNext: $("#greeting-next"), greetingWarning: $("#greeting-warning"), greetingPlanCancel: $("#greeting-plan-cancel"), greetingLogList: $("#greeting-log-list"), greetingLogCount: $("#greeting-log-count"),
  knowledgeButton: $("#knowledge-button"), knowledgeDrawer: $("#knowledge-drawer"), knowledgeClose: $("#knowledge-close"),
  knowledgeList: $("#knowledge-list"), knowledgeCount: $("#knowledge-count"), knowledgeForm: $("#knowledge-form"), knowledgeId: $("#knowledge-id"),
  knowledgeTitle: $("#knowledge-title"), knowledgeKeywords: $("#knowledge-keywords"), knowledgeContent: $("#knowledge-content"),
  knowledgeEnabled: $("#knowledge-enabled"), knowledgeCancel: $("#knowledge-cancel"), knowledgeFeedback: $("#knowledge-feedback"),
  candidateDialog: $("#candidate-dialog"), newCandidateForm: $("#new-candidate-form"), candidateDialogClose: $("#candidate-dialog-close"),
  newName: $("#new-name"), newJob: $("#new-job"), newWechat: $("#new-wechat"), newCandidateFeedback: $("#new-candidate-feedback"), toast: $("#toast"),
};

const stageLabels = { new: "新线索", contacted: "已沟通", private: "已进私域", interview: "待面试", hired: "已录用", closed: "已结束" };
const avatarPalette = ["#008f8a", "#dc6847", "#356a9a", "#6d7052", "#b98519"];
let toastTimer = null;

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function avatarColor(name) {
  const total = Array.from(name || "候").reduce((sum, char) => sum + char.codePointAt(0), 0);
  return avatarPalette[total % avatarPalette.length];
}

function initials(name) { return Array.from((name || "候选").trim()).slice(-2).join(""); }

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elements.toast.classList.add("hidden"), 2500);
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  let data = {};
  try { data = await response.json(); } catch (_error) { data = {}; }
  if (response.status === 401) { showLogin(); throw new Error(data.detail || "登录已失效"); }
  if (!response.ok) { const error = new Error(data.detail || `请求失败 (${response.status})`); error.code = data.code; throw error; }
  return data;
}

function showLogin() {
  elements.appView.classList.add("hidden"); elements.loginView.classList.remove("hidden"); elements.password.value = "";
  setTimeout(() => elements.password.focus(), 0);
}

function showApp() { elements.loginView.classList.add("hidden"); elements.appView.classList.remove("hidden"); }

function setActiveRail(button) {
  for (const item of [elements.conversationButton, elements.taskButton, elements.greetingButton, elements.knowledgeButton]) item.classList.toggle("active", item === button);
}

function updateSendState() {
  const available = state.channel === "wechat" || (state.connected && state.loggedIn);
  elements.sendButton.disabled = !available || state.sending || !state.selected;
}

function updateConnection(status) {
  state.connected = Boolean(status.connected); state.loggedIn = Boolean(status.logged_in);
  const online = state.connected && state.loggedIn;
  elements.railStatus.classList.toggle("online", online);
  if (state.channel === "boss") {
    elements.connectionChip.textContent = online ? "BOSS 已连接" : "BOSS 未连接";
    elements.connectionChip.classList.toggle("online", online); elements.connectionChip.classList.toggle("offline", !online);
    if (!online) { elements.statusBanner.textContent = status.message || "请在调试 Chrome 中登录 BOSS"; elements.statusBanner.classList.remove("hidden"); }
    else elements.statusBanner.classList.add("hidden");
  } else {
    elements.connectionChip.textContent = "微信适配器 · 本地"; elements.connectionChip.classList.add("online"); elements.connectionChip.classList.remove("offline");
    elements.statusBanner.classList.add("hidden");
  }
  updateSendState();
}

async function loadSystemStatus() {
  try { updateConnection(await api("/api/status")); } catch (error) { updateConnection({ connected: false, logged_in: false, message: error.message }); }
  try {
    const status = await api("/api/ai/status"); state.aiConfigured = Boolean(status.configured);
    elements.aiChip.textContent = state.aiConfigured ? status.model : "Kimi 未配置"; elements.aiChip.classList.toggle("online", state.aiConfigured);
  } catch (_error) { elements.aiChip.textContent = "Kimi 不可用"; }
  try {
    const status = await api("/api/knowledge/status"); state.semanticReady = Boolean(status.ready);
    elements.semanticChip.textContent = state.semanticReady ? "BGE 语义检索" : "词法检索降级"; elements.semanticChip.classList.toggle("online", state.semanticReady);
  } catch (_error) { elements.semanticChip.textContent = "检索状态未知"; }
}

function renderCandidates() {
  const query = elements.search.value.trim().toLowerCase();
  const candidates = state.candidates.filter((item) => `${item.name} ${item.job}`.toLowerCase().includes(query));
  elements.contactList.replaceChildren(); elements.contactCount.textContent = `${state.candidates.length} 位`;
  if (!candidates.length) {
    elements.contactList.append(createElement("p", "list-state", query ? "没有匹配的候选人" : state.channel === "wechat" ? "尚未绑定微信候选人，点击右上角新增或在档案中绑定。" : "当前没有 BOSS 会话。"));
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const candidate of candidates) {
    const row = createElement("div", "contact-row");
    const item = createElement("button", "contact-item"); item.type = "button"; item.dataset.id = candidate.id;
    item.classList.toggle("selected", candidate.id === state.selectedId);
    const avatar = createElement("span", "contact-avatar", initials(candidate.name)); avatar.style.backgroundColor = avatarColor(candidate.name);
    const copy = createElement("span", "contact-copy"); const nameRow = createElement("span", "contact-name-row");
    nameRow.append(createElement("span", "contact-name", candidate.name), createElement("span", "mini-stage", stageLabels[candidate.stage] || "新线索"));
    copy.append(nameRow, createElement("span", "contact-job", candidate.job || "未标注岗位"), createElement("span", "contact-preview", candidate.last_message || (state.channel === "wechat" ? candidate.wechat_id : "暂无消息")));
    item.append(avatar, copy, createElement("span", "contact-time", candidate.last_active || ""));
    item.addEventListener("click", () => selectContact(candidate.id)); row.append(item);
    if (state.channel === "boss") {
      const actions = createElement("details", "contact-actions"); const more = createElement("summary", "contact-more", "···");
      more.setAttribute("aria-label", `${candidate.name} 更多操作`); more.title = "更多操作";
      const menu = createElement("div", "contact-menu"); const remove = createElement("button", "contact-delete", "删除"); remove.type = "button";
      remove.addEventListener("click", () => deleteBossConversation(candidate, remove, actions));
      actions.addEventListener("toggle", () => { if (actions.open) for (const open of elements.contactList.querySelectorAll(".contact-actions[open]")) if (open !== actions) open.removeAttribute("open"); });
      menu.append(remove); actions.append(more, menu); row.append(actions);
    }
    fragment.append(row);
  }
  elements.contactList.append(fragment);
}

async function loadCandidates(preserveSelection = true) {
  const previous = preserveSelection ? state.selectedId : null;
  state.candidates = await api(`/api/candidates?channel=${state.channel}`);
  state.selectedId = state.candidates.some((item) => item.id === previous) ? previous : null;
  state.selected = state.candidates.find((item) => item.id === state.selectedId) || null;
  renderCandidates();
  if (!state.selected) showEmptyConversation();
}

function showEmptyConversation() {
  state.selectedId = null; state.selected = null; state.messages = [];
  elements.emptyConversation.classList.remove("hidden"); elements.conversationView.classList.add("hidden");
  elements.contextEmpty.classList.remove("hidden"); elements.contextContent.classList.add("hidden"); elements.candidateId.textContent = "未选择";
  clearDraft(); updateSendState();
}

function renderMessages() {
  elements.messageList.replaceChildren();
  if (!state.messages.length) { elements.messageList.append(createElement("p", "list-state", "当前渠道还没有消息。")); return; }
  const fragment = document.createDocumentFragment();
  for (const message of state.messages) {
    const sender = message.sender || "system"; const row = createElement("div", `message-row ${sender}`);
    row.append(createElement("div", "message-bubble", message.text || ""));
    const detail = createElement("div", "message-detail"); detail.append(createElement("span", "", message.time || message.created_at || ""));
    if (message.status) detail.append(createElement("span", "", message.status)); row.append(detail); fragment.append(row);
  }
  elements.messageList.append(fragment); elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function renderContext() {
  const candidate = state.selected;
  if (!candidate) return;
  elements.contextEmpty.classList.add("hidden"); elements.contextContent.classList.remove("hidden"); elements.candidateId.textContent = `ID ${candidate.id}`;
  elements.candidateStage.value = candidate.stage || "new"; elements.candidateName.value = candidate.name || ""; elements.candidateJob.value = candidate.job || "";
  elements.wechatId.value = candidate.wechat_id || ""; elements.privateContact.value = candidate.private_contact || "";
  elements.candidateTags.value = (candidate.tags || []).join(", "); elements.candidateNotes.value = candidate.notes || "";
  elements.activeName.textContent = candidate.name; elements.activeJob.textContent = candidate.job || "未标注岗位";
  elements.activeStage.textContent = stageLabels[candidate.stage] || "新线索"; elements.activeAvatar.textContent = initials(candidate.name); elements.activeAvatar.style.backgroundColor = avatarColor(candidate.name);
  elements.composerRecipient.textContent = candidate.name;
}

function latestIncoming() {
  return [...state.messages].reverse().find((item) => ["contact", "candidate", "me", "agent"].includes(item.sender));
}

async function loadConversation({ draft = true, activate = false } = {}) {
  if (!state.selected) return;
  const candidateId = state.selected.id; const channel = state.channel;
  const messages = await api(`/api/candidates/${candidateId}/messages?channel=${channel}&activate=${activate}`);
  if (!state.selected || state.selected.id !== candidateId || state.channel !== channel) return;
  state.messages = messages;
  renderMessages();
  if (draft) {
    const latest = latestIncoming();
    if (latest && ["contact", "candidate"].includes(latest.sender)) {
      const signature = `${state.channel}:${state.selected.id}:${latest.text}:${latest.time || latest.created_at || ""}`;
      if (signature !== state.draftSignature && !state.ignoredDrafts.has(signature)) generateDraft(false, signature);
    } else clearDraft();
  }
}

async function selectContact(candidateId) {
  const candidate = state.candidates.find((item) => item.id === Number(candidateId)); if (!candidate) return;
  state.selectedId = candidate.id; state.selected = candidate; state.messageMode = "reply";
  state.messages = []; elements.messageInput.value = "";
  clearDraft(); renderCandidates(); renderContext(); updateMessageMode();
  renderMessages();
  elements.emptyConversation.classList.add("hidden"); elements.conversationView.classList.remove("hidden"); updateConnection({ connected: state.connected, logged_in: state.loggedIn, message: "" });
  try { await loadConversation({ activate: true }); } catch (error) { showToast(error.message); }
}

async function deleteBossConversation(candidate, button, actions) {
  if (!window.confirm(`确定删除 BOSS 会话“${candidate.name}”吗？\n本地候选人档案和微信记录会保留。`)) return;
  button.disabled = true; button.textContent = "删除中…";
  try {
    await api(`/api/candidates/${candidate.id}/boss-conversation`, { method: "DELETE" });
    actions.removeAttribute("open"); await loadCandidates(true); showToast("BOSS 会话已删除");
  } catch (error) {
    button.disabled = false; button.textContent = "删除"; showToast(error.message);
  }
}

function adoptDraft() {
  if (!state.draft || !state.draft.text) return;
  state.messageMode = "reply"; updateMessageMode(); elements.messageInput.value = state.draft.text; elements.messageInput.focus();
}

function clearDraft() { state.draft = null; elements.draftPanel.classList.add("hidden"); elements.draftText.textContent = ""; elements.draftSources.textContent = ""; }

async function generateDraft(force = false, signature = null) {
  if (!state.selected || !state.aiConfigured) return;
  elements.draftPanel.classList.remove("hidden"); elements.draftStatus.textContent = "正在生成"; elements.draftText.textContent = "";
  elements.adoptDraft.disabled = true; elements.regenerateDraft.disabled = true;
  try {
    const result = await api(`/api/candidates/${state.selected.id}/draft`, { method: "POST", body: JSON.stringify({ channel: state.channel, force }) });
    state.draft = result; state.draftSignature = signature || result.fingerprint || state.draftSignature;
    elements.draftStatus.textContent = result.status === "ready" ? "已生成，等待审核" : result.reason || "需要人工处理";
    elements.draftText.textContent = result.text || result.reason || "未生成草稿";
    elements.draftSources.textContent = result.sources?.length ? `依据：${result.sources.map((source) => source.title).join(" · ")}` : "未引用知识条目";
    elements.adoptDraft.disabled = result.status !== "ready";
  } catch (error) { elements.draftStatus.textContent = error.message; elements.draftText.textContent = "草稿生成失败"; }
  finally { elements.regenerateDraft.disabled = false; }
}

function ignoreDraft() { if (state.draftSignature) state.ignoredDrafts.add(state.draftSignature); clearDraft(); }

function updateMessageMode() {
  const wechat = state.channel === "wechat"; elements.messageMode.classList.toggle("hidden", !wechat);
  elements.modeReply.classList.toggle("active", state.messageMode === "reply"); elements.modeIncoming.classList.toggle("active", state.messageMode === "incoming");
  elements.sendButton.textContent = state.messageMode === "incoming" ? "记录消息" : "发送";
  elements.messageInput.placeholder = state.messageMode === "incoming" ? "录入候选人从微信发来的消息" : "输入回复，发送前请确认内容";
}

async function sendMessage() {
  const text = elements.messageInput.value.trim(); if (!text || !state.selected || state.sending) return;
  state.sending = true; elements.sendFeedback.textContent = state.messageMode === "incoming" ? "正在记录" : "正在发送"; updateSendState();
  try {
    if (state.channel === "boss") await api(`/api/contacts/${encodeURIComponent(state.selected.boss_key)}/messages`, { method: "POST", body: JSON.stringify({ text }) });
    else await api(`/api/candidates/${state.selected.id}/messages`, { method: "POST", body: JSON.stringify({ channel: "wechat", sender: state.messageMode === "incoming" ? "candidate" : "agent", text }) });
    elements.messageInput.value = ""; elements.sendFeedback.textContent = state.messageMode === "incoming" ? "已记录" : "已发送";
    state.draftSignature = null; clearDraft(); await loadConversation(); await loadCandidates(true);
  } catch (error) { elements.sendFeedback.textContent = error.message; showToast(error.message); }
  finally { state.sending = false; updateSendState(); setTimeout(() => { elements.sendFeedback.textContent = ""; }, 1800); }
}

async function switchAgent(channel) {
  if (state.channel === channel) return;
  state.channel = channel; state.messageMode = "reply"; state.selectedId = null; state.selected = null;
  elements.bossTab.classList.toggle("active", channel === "boss"); elements.wechatTab.classList.toggle("active", channel === "wechat");
  elements.bossTab.setAttribute("aria-selected", String(channel === "boss")); elements.wechatTab.setAttribute("aria-selected", String(channel === "wechat"));
  elements.channelCaption.textContent = channel === "boss" ? "来自 BOSS 的实时会话" : "私域跟进会话";
  elements.newCandidateButton.classList.toggle("hidden", channel !== "wechat"); updateMessageMode(); await loadCandidates(false); await loadSystemStatus();
}

async function saveCandidate(event) {
  event.preventDefault(); if (!state.selected) return;
  const payload = { name: elements.candidateName.value, job: elements.candidateJob.value, stage: elements.candidateStage.value, wechat_id: elements.wechatId.value, private_contact: elements.privateContact.value, tags: elements.candidateTags.value.split(/[,，]/).map((item) => item.trim()).filter(Boolean), notes: elements.candidateNotes.value };
  try { state.selected = await api(`/api/candidates/${state.selected.id}`, { method: "PATCH", body: JSON.stringify(payload) }); state.selectedId = state.selected.id; await loadCandidates(true); renderContext(); showToast("候选人档案已保存"); }
  catch (error) { showToast(error.message); }
}

async function scheduleInterview(event) {
  event.preventDefault(); if (!state.selected) return;
  try {
    await api(`/api/candidates/${state.selected.id}/interviews`, { method: "POST", body: JSON.stringify({ starts_at: elements.interviewTime.value, location: elements.interviewLocation.value }) });
    elements.interviewForm.reset(); await Promise.all([loadTasks(), loadCandidates(true)]); state.selected = state.candidates.find((item) => item.id === state.selectedId); renderContext(); showToast("已生成 BOSS 确认任务，等待人工审核"); openTasks();
  } catch (error) { showToast(error.message); }
}

async function loadTasks() {
  state.tasks = await api("/api/tasks?status=pending_review"); elements.taskBadge.textContent = String(state.tasks.length); elements.taskBadge.classList.toggle("hidden", !state.tasks.length); renderTasks();
}

function renderTasks() {
  elements.taskList.replaceChildren();
  if (!state.tasks.length) { elements.taskList.append(createElement("p", "list-state", "没有待审核的跨 Agent 任务。")); return; }
  for (const task of state.tasks) {
    const item = createElement("article", "task-item"); const head = createElement("div", "task-item-head");
    head.append(createElement("h3", "", `${task.candidate_name} · ${task.candidate_job || "未标注岗位"}`), createElement("span", "knowledge-state enabled", "待审核"));
    const meta = createElement("p", "task-meta", "微信 Agent 已确认面试，需由 BOSS Agent 再次确认。");
    const draft = document.createElement("textarea"); draft.className = "task-draft"; draft.value = task.draft; draft.maxLength = 2000; draft.setAttribute("aria-label", "待发送确认消息");
    const actions = createElement("div", "task-actions"); const dismiss = createElement("button", "secondary-button", "忽略"); dismiss.type = "button";
    const send = createElement("button", "primary-small-button", "审核并发送"); send.type = "button";
    dismiss.addEventListener("click", async () => { await api(`/api/tasks/${task.id}/dismiss`, { method: "POST" }); await loadTasks(); });
    send.addEventListener("click", async () => {
      if (!window.confirm(`确认通过审核并发送给 ${task.candidate_name}？`)) return;
      send.disabled = true;
      try { await api(`/api/tasks/${task.id}/send`, { method: "POST", body: JSON.stringify({ text: draft.value }) }); showToast("BOSS 确认消息已发送"); await loadTasks(); }
      catch (error) { showToast(error.message); send.disabled = false; }
    });
    actions.append(dismiss, send); item.append(head, meta, draft, actions); elements.taskList.append(item);
  }
}

function closeDrawers() { elements.taskDrawer.classList.add("hidden"); elements.greetingDrawer.classList.add("hidden"); elements.knowledgeDrawer.classList.add("hidden"); elements.drawerBackdrop.classList.add("hidden"); }

async function switchBossView(view) {
  return api(view === "chat" ? "/api/boss/view/chat" : "/api/boss/view/recommend", { method: "POST" });
}

async function closeActiveDrawer() {
  const restoreChat = !elements.greetingDrawer.classList.contains("hidden");
  closeDrawers(); setActiveRail(elements.conversationButton);
  if (!restoreChat) return;
  try { await switchBossView("chat"); await loadSystemStatus(); }
  catch (error) { showToast(error.message); }
}

async function openConversations() {
  closeDrawers(); setActiveRail(elements.conversationButton);
  try {
    await switchBossView("chat");
    if (state.channel !== "boss") await switchAgent("boss");
    else { await loadCandidates(true); if (state.selected) await loadConversation({ activate: true }); await loadSystemStatus(); }
    showToast("BOSS 已切回沟通");
  } catch (error) { showToast(error.message); }
}

async function openTasks() { await closeActiveDrawer(); setActiveRail(elements.taskButton); await loadTasks(); elements.taskDrawer.classList.remove("hidden"); elements.drawerBackdrop.classList.remove("hidden"); }

async function loadGreetings() {
  const [status, logs] = await Promise.all([api("/api/greeting-plans"), api("/api/greetings/logs")]);
  state.greetings = status; state.greetingLogs = logs; renderGreetings();
}

function greetingTime(value) { return (value || "").replace("T", " "); }

function localMinute(value) {
  const pad = (number) => String(number).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}

function renderGreetings() {
  if (!state.greetings) return;
  const status = state.greetings; const plans = status.plans || []; const enabled = plans.filter((plan) => plan.enabled);
  const next = plans.find((plan) => plan.due) || enabled.filter((plan) => plan.next_run).sort((a, b) => a.next_run.localeCompare(b.next_run))[0];
  elements.greetingToday.textContent = String(status.today_sent); elements.greetingHour.textContent = String(status.hour_sent);
  elements.greetingNext.textContent = next ? (next.due ? "等待执行" : next.next_run.slice(5, 19).replace("T", " ")) : enabled.length ? "暂无" : "无计划";
  elements.greetingBadge.textContent = enabled.length ? String(enabled.length) : "停"; elements.greetingBadge.classList.remove("hidden");
  elements.greetingPlanCount.textContent = `${plans.length} 个`; elements.greetingPlanList.replaceChildren();
  if (!plans.length) elements.greetingPlanList.append(createElement("p", "list-state", "暂无主动招呼计划。"));
  const windowLabels = { disabled: "已停用", pending: "待开始", active: "运行中", ended: "已结束" };
  for (const plan of plans) {
    const item = createElement("article", "greeting-plan"); const head = createElement("div", "greeting-plan-head");
    const stateText = plan.paused_reason ? "已暂停" : windowLabels[plan.window_state] || "已停用";
    const stateClass = plan.paused_reason ? "paused" : plan.enabled && plan.window_state !== "ended" ? "active" : "";
    head.append(createElement("h3", "", plan.name), createElement("span", `greeting-plan-state ${stateClass}`, stateText));
    const windowText = `${greetingTime(plan.start_at)}  至  ${greetingTime(plan.end_at)}`;
    const nextText = plan.due ? " · 当前到期" : plan.next_run ? ` · 下次 ${greetingTime(plan.next_run)}` : "";
    item.append(head, createElement("p", "greeting-plan-window", windowText), createElement("p", "greeting-plan-quota", `每日 ${plan.daily_limit} · 每小时 ${plan.hourly_limit}${nextText}`));
    if (plan.paused_reason) item.append(createElement("p", "greeting-plan-reason", plan.paused_reason));
    const actions = createElement("div", "greeting-plan-actions"); const toggleLabel = createElement("label", "plan-toggle"); const toggle = document.createElement("input");
    toggle.type = "checkbox"; toggle.checked = plan.enabled; toggle.disabled = status.running; toggle.setAttribute("aria-label", `${plan.name}启用状态`);
    toggle.addEventListener("change", () => toggleGreetingPlan(plan, toggle.checked)); toggleLabel.append(toggle, document.createTextNode("启用"));
    const edit = createElement("button", "text-button", "编辑"); edit.type = "button"; edit.addEventListener("click", () => openGreetingForm(plan));
    const run = createElement("button", "text-button", "执行一次"); run.type = "button"; run.disabled = status.running || !plan.manual_due; run.title = plan.manual_due ? "立即执行一次" : "仅可在计划时段且额度未用完时执行"; run.addEventListener("click", () => runGreetingPlan(plan, run));
    const remove = createElement("button", "text-button danger", "删除"); remove.type = "button"; remove.disabled = status.running; remove.addEventListener("click", () => deleteGreetingPlan(plan));
    actions.append(toggleLabel, edit, run, remove); item.append(actions); elements.greetingPlanList.append(item);
  }

  elements.greetingLogList.replaceChildren(); elements.greetingLogCount.textContent = `${state.greetingLogs.length} 条`;
  if (!state.greetingLogs.length) { elements.greetingLogList.append(createElement("p", "list-state", "暂无执行记录。")); return; }
  for (const log of state.greetingLogs) {
    const item = createElement("div", `greeting-log ${log.status}`); const mark = createElement("span", "greeting-log-mark", log.status === "sent" ? "✓" : "!");
    const detail = [log.plan_name, log.summary || log.reason].filter(Boolean).join(" · ");
    const copy = createElement("span", "greeting-log-copy"); copy.append(createElement("strong", "", log.candidate_name || (log.status === "sent" ? "已打招呼" : "执行失败")), createElement("span", "", detail));
    item.append(mark, copy, createElement("span", "greeting-log-time", (log.created_at || "").replace("T", " ").slice(5, 16))); elements.greetingLogList.append(item);
  }
}

async function openGreetings() {
  await closeActiveDrawer(); closeGreetingForm(); setActiveRail(elements.greetingButton); await loadGreetings();
  elements.greetingDrawer.classList.remove("hidden"); elements.drawerBackdrop.classList.remove("hidden");
  try { await switchBossView("recommend"); await loadSystemStatus(); showToast("BOSS 已切到推荐牛人"); }
  catch (error) { showToast(error.message); }
}

function openGreetingForm(plan = null) {
  const start = new Date(); start.setSeconds(0, 0); const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
  elements.greetingPlanId.value = plan?.id || ""; elements.greetingFormHeading.textContent = plan ? "编辑计划" : "新建计划";
  elements.greetingPlanName.value = plan?.name || ""; elements.greetingEnabled.checked = plan?.enabled || false;
  elements.greetingDailyLimit.value = plan?.daily_limit || 30; elements.greetingHourlyLimit.value = plan?.hourly_limit || 4;
  elements.greetingStartAt.value = plan?.start_at || localMinute(start); elements.greetingEndAt.value = plan?.end_at || localMinute(end);
  elements.greetingWarning.textContent = ""; elements.greetingWarning.classList.remove("error"); validateGreetingWindow();
  elements.greetingForm.classList.remove("hidden"); elements.greetingForm.scrollIntoView({ block: "start" }); elements.greetingPlanName.focus();
}

function closeGreetingForm() { elements.greetingForm.classList.add("hidden"); elements.greetingWarning.textContent = ""; }

function validateGreetingWindow() {
  const startAt = elements.greetingStartAt.value; const endAt = elements.greetingEndAt.value;
  elements.greetingEndAt.min = startAt;
  elements.greetingEndAt.setCustomValidity(startAt && endAt && endAt <= startAt ? "结束时间必须晚于开始时间" : "");
}

async function saveGreetingPlan(event) {
  event.preventDefault();
  validateGreetingWindow(); if (!elements.greetingForm.reportValidity()) return;
  const id = elements.greetingPlanId.value; const payload = { name: elements.greetingPlanName.value, enabled: elements.greetingEnabled.checked, daily_limit: Number(elements.greetingDailyLimit.value), hourly_limit: Number(elements.greetingHourlyLimit.value), start_at: elements.greetingStartAt.value, end_at: elements.greetingEndAt.value };
  try { await api(id ? `/api/greeting-plans/${id}` : "/api/greeting-plans", { method: id ? "PATCH" : "POST", body: JSON.stringify(payload) }); closeGreetingForm(); await loadGreetings(); showToast(id ? "计划已更新" : "计划已创建"); }
  catch (error) { elements.greetingWarning.textContent = error.message; elements.greetingWarning.classList.add("error"); showToast(error.message); }
}

async function toggleGreetingPlan(plan, enabled) {
  try { await api(`/api/greeting-plans/${plan.id}`, { method: "PATCH", body: JSON.stringify({ enabled }) }); showToast(enabled ? "计划已启用" : "计划已停用"); }
  catch (error) { showToast(error.message); }
  finally { await loadGreetings(); }
}

async function runGreetingPlan(plan, run) {
  run.disabled = true; run.textContent = "执行中…"; showToast("正在切换 BOSS 并打招呼");
  try { const candidate = await api(`/api/greeting-plans/${plan.id}/run-once`, { method: "POST" }); showToast(`已向 ${candidate.name || "候选人"} 打招呼`); }
  catch (error) { showToast(error.message); }
  finally { await loadGreetings(); }
}

async function deleteGreetingPlan(plan) {
  if (!window.confirm(`删除“${plan.name}”？`)) return;
  try { await api(`/api/greeting-plans/${plan.id}`, { method: "DELETE" }); if (elements.greetingPlanId.value === String(plan.id)) closeGreetingForm(); await loadGreetings(); showToast("计划已删除"); }
  catch (error) { showToast(error.message); }
}

function resetKnowledgeForm() { elements.knowledgeForm.reset(); elements.knowledgeId.value = ""; elements.knowledgeEnabled.checked = true; elements.knowledgeCancel.classList.add("hidden"); elements.knowledgeFeedback.textContent = ""; }
async function loadKnowledge() { state.knowledge = await api("/api/knowledge"); renderKnowledge(); }
function renderKnowledge() {
  elements.knowledgeList.replaceChildren(); elements.knowledgeCount.textContent = `${state.knowledge.length} 条`;
  if (!state.knowledge.length) { elements.knowledgeList.append(createElement("p", "list-state", "知识库为空。")); return; }
  for (const entry of state.knowledge) {
    const item = createElement("article", "knowledge-item"); const head = createElement("div", "knowledge-item-head");
    head.append(createElement("h3", "", entry.title), createElement("span", `knowledge-state ${entry.enabled ? "enabled" : ""}`, entry.enabled ? "检索中" : "已停用"));
    item.append(head, createElement("p", "knowledge-copy", entry.content), createElement("p", "knowledge-keywords", entry.keywords ? `常见说法：${entry.keywords}` : "未设置常见说法"));
    const actions = createElement("div", "knowledge-actions"); const edit = createElement("button", "text-button", "编辑"); const remove = createElement("button", "text-button danger", "删除");
    edit.type = remove.type = "button";
    edit.addEventListener("click", () => { elements.knowledgeId.value = entry.id; elements.knowledgeTitle.value = entry.title; elements.knowledgeKeywords.value = entry.keywords; elements.knowledgeContent.value = entry.content; elements.knowledgeEnabled.checked = entry.enabled; elements.knowledgeCancel.classList.remove("hidden"); });
    remove.addEventListener("click", async () => { if (!window.confirm(`删除“${entry.title}”？`)) return; await api(`/api/knowledge/${entry.id}`, { method: "DELETE" }); await loadKnowledge(); });
    actions.append(edit, remove); item.append(actions); elements.knowledgeList.append(item);
  }
}
async function openKnowledge() { await closeActiveDrawer(); setActiveRail(elements.knowledgeButton); await loadKnowledge(); elements.knowledgeDrawer.classList.remove("hidden"); elements.drawerBackdrop.classList.remove("hidden"); }
async function saveKnowledge(event) {
  event.preventDefault(); const id = elements.knowledgeId.value; const payload = { title: elements.knowledgeTitle.value, keywords: elements.knowledgeKeywords.value, content: elements.knowledgeContent.value, enabled: elements.knowledgeEnabled.checked };
  try { await api(id ? `/api/knowledge/${id}` : "/api/knowledge", { method: id ? "PATCH" : "POST", body: JSON.stringify(payload) }); resetKnowledgeForm(); await loadKnowledge(); await loadSystemStatus(); showToast("知识已保存并更新索引"); }
  catch (error) { elements.knowledgeFeedback.textContent = error.message; }
}

async function createCandidate(event) {
  event.preventDefault(); elements.newCandidateFeedback.textContent = "";
  try { const candidate = await api("/api/candidates", { method: "POST", body: JSON.stringify({ name: elements.newName.value, job: elements.newJob.value, wechat_id: elements.newWechat.value }) }); elements.candidateDialog.close(); elements.newCandidateForm.reset(); if (state.channel !== "wechat") await switchAgent("wechat"); else await loadCandidates(false); await selectContact(candidate.id); }
  catch (error) { elements.newCandidateFeedback.textContent = error.message; }
}

async function poll() {
  if (state.polling || elements.appView.classList.contains("hidden")) return;
  state.polling = true; state.pollCount += 1;
  try { await loadSystemStatus(); if (state.pollCount % 2 === 0) await Promise.all([loadTasks(), loadGreetings()]); if (state.pollCount % 3 === 0) { await loadCandidates(true); if (state.selected) await loadConversation(); } }
  finally { state.polling = false; }
}

elements.loginForm.addEventListener("submit", async (event) => { event.preventDefault(); elements.loginError.textContent = ""; try { await api("/api/login", { method: "POST", body: JSON.stringify({ username: elements.username.value, password: elements.password.value }) }); showApp(); await Promise.all([loadSystemStatus(), loadCandidates(false), loadTasks(), loadGreetings()]); } catch (error) { elements.loginError.textContent = error.message; } });
elements.logoutButton.addEventListener("click", async () => { try { await api("/api/logout", { method: "POST" }); } finally { showLogin(); } });
elements.refreshButton.addEventListener("click", async () => { await loadCandidates(true); if (state.selected) await loadConversation(); });
elements.search.addEventListener("input", renderCandidates); elements.bossTab.addEventListener("click", () => switchAgent("boss")); elements.wechatTab.addEventListener("click", () => switchAgent("wechat"));
elements.newCandidateButton.addEventListener("click", () => elements.candidateDialog.showModal()); elements.candidateDialogClose.addEventListener("click", () => elements.candidateDialog.close()); elements.newCandidateForm.addEventListener("submit", createCandidate);
elements.sendButton.addEventListener("click", sendMessage); elements.adoptDraft.addEventListener("click", adoptDraft); elements.regenerateDraft.addEventListener("click", () => generateDraft(true)); elements.ignoreDraft.addEventListener("click", ignoreDraft);
elements.modeReply.addEventListener("click", () => { state.messageMode = "reply"; updateMessageMode(); }); elements.modeIncoming.addEventListener("click", () => { state.messageMode = "incoming"; clearDraft(); updateMessageMode(); });
elements.candidateForm.addEventListener("submit", saveCandidate); elements.interviewForm.addEventListener("submit", scheduleInterview);
elements.conversationButton.addEventListener("click", openConversations); elements.taskButton.addEventListener("click", openTasks); elements.taskClose.addEventListener("click", closeActiveDrawer); elements.greetingButton.addEventListener("click", openGreetings); elements.greetingClose.addEventListener("click", closeActiveDrawer); elements.greetingNewPlan.addEventListener("click", () => openGreetingForm()); elements.greetingPlanCancel.addEventListener("click", closeGreetingForm); elements.greetingForm.addEventListener("submit", saveGreetingPlan); elements.knowledgeButton.addEventListener("click", openKnowledge); elements.knowledgeClose.addEventListener("click", closeActiveDrawer); elements.drawerBackdrop.addEventListener("click", closeActiveDrawer);
elements.greetingStartAt.addEventListener("input", validateGreetingWindow); elements.greetingEndAt.addEventListener("input", validateGreetingWindow);
elements.knowledgeForm.addEventListener("submit", saveKnowledge); elements.knowledgeCancel.addEventListener("click", resetKnowledgeForm);
elements.messageInput.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage(); } });
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeActiveDrawer(); });

async function start() {
  elements.newCandidateButton.classList.add("hidden");
  try { await api("/api/me"); showApp(); await Promise.all([loadSystemStatus(), loadCandidates(false), loadTasks(), loadGreetings()]); }
  catch (_error) { showLogin(); }
  setInterval(poll, 5000);
}

start();
