import { apiUrl, getAgentHeaders } from "@/lib/config";

export interface RecruitmentRequirement {
  id: number;
  title: string;
  role: string;
  job_category: string;
  location: string;
  search_keyword: string;
  education_requirement: string;
  age_requirement: string;
  recommended_filters: string;
  sort_preference: string;
  filter_viewed_14_days: boolean;
  filter_exchanged_30_days: boolean;
  batch_size: number;
  tags: string;
  must_have: string;
  nice_have: string;
  description: string;
  status: "active" | "paused" | "closed";
  owner_id: number;
  created_at: string;
  updated_at: string;
}

export interface RecruitmentCandidate {
  id: number;
  requirement_id: number;
  owner_id: number;
  name: string;
  source: string;
  current_role: string;
  location: string;
  tags: string;
  profile: string;
  match_score: number;
  match_reason: string;
  contact_status: "new" | "contacted" | "replied" | "consented" | "group_invited" | "rejected";
  consent_to_contact: boolean;
  private_contact: string;
  group_status: "not_invited" | "invited" | "joined" | "not_joined";
  last_message: string;
  next_action: string;
  created_at: string;
  updated_at: string;
}

export type CreateRequirementPayload = Pick<
  RecruitmentRequirement,
  | "title"
  | "role"
  | "job_category"
  | "location"
  | "search_keyword"
  | "education_requirement"
  | "age_requirement"
  | "recommended_filters"
  | "sort_preference"
  | "filter_viewed_14_days"
  | "filter_exchanged_30_days"
  | "batch_size"
  | "tags"
  | "must_have"
  | "nice_have"
  | "description"
  | "status"
>;

export type CreateCandidatePayload = Pick<
  RecruitmentCandidate,
  "requirement_id" | "name" | "source" | "current_role" | "location" | "tags" | "profile"
>;

export type UpdateCandidatePayload = Partial<
  Pick<
    RecruitmentCandidate,
    | "name"
    | "source"
    | "current_role"
    | "location"
    | "tags"
    | "profile"
    | "contact_status"
    | "consent_to_contact"
    | "private_contact"
    | "group_status"
    | "last_message"
    | "next_action"
  >
>;

export interface BossAssistantStatus {
  detected: boolean;
  saved_exe_path: string;
  exe_path: string;
  process_id: number;
  process_name: string;
  window_title: string;
  visible: boolean;
  minimized: boolean;
  window_left: number;
  window_top: number;
  window_width: number;
  window_height: number;
  last_checked_at: string;
  message: string;
}

export type BossMenu = "job" | "recommend" | "search" | "chat";

export interface BossMenuClickResult {
  menu: BossMenu;
  output: string;
  message: string;
}

export interface BossSearchResult {
  output: string;
  message: string;
}

export interface BossImportCandidatesResult {
  candidates: RecruitmentCandidate[];
  imported: number;
  skipped: number;
  message: string;
}

export interface RecruitmentAgentEvent {
  step: string;
  status: string;
  message: string;
}

// Chat Draft API — 调用 POST /agent/recruitment/chat-draft

export interface ChatMessage {
  role: "candidate" | "recruiter";
  content: string;
}

export interface ChatDraftInput {
  requirement_id: number;
  candidate_id: number;
  messages: ChatMessage[];
}

export interface ChatDraftResult {
  draft: string;
  follow_up_questions: string[];
  scene: string;
}

export interface ChatDraftResponse {
  result: ChatDraftResult;
}

export interface RecruitmentAgentResult {
  thread_id: string;
  stage: string;
  match_score: number;
  match_reason: string;
  draft: string;
  next_action: string;
  requires_human_approval: boolean;
  mode: string;
  events: RecruitmentAgentEvent[];
}

export interface RecruitmentTimelineEvent {
  id: number;
  candidate_id: number;
  owner_id: number;
  event_type: string;
  title: string;
  content: string;
  from_status: string;
  to_status: string;
  created_at: string;
}

export interface CreateTimelineEventPayload {
  event_type?: string;
  title?: string;
  content: string;
  from_status?: string;
  to_status?: string;
}

async function parseApiError(res: Response, fallback: string): Promise<Error> {
  const err = await res.json().catch(() => ({}));
  return new Error((err as { error?: string }).error || fallback);
}

export async function fetchRecruitmentRequirements(): Promise<RecruitmentRequirement[]> {
  const res = await fetch(apiUrl("/agent/recruitment/requirements"), {
    cache: "no-store",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "获取招聘需求失败");
  const data: { requirements?: RecruitmentRequirement[] } = await res.json();
  return data.requirements ?? [];
}

export async function createRecruitmentRequirement(
  payload: CreateRequirementPayload
): Promise<RecruitmentRequirement> {
  const res = await fetch(apiUrl("/agent/recruitment/requirements"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseApiError(res, "创建招聘需求失败");
  const data: { requirement: RecruitmentRequirement } = await res.json();
  return data.requirement;
}

export async function updateRecruitmentRequirement(
  id: number,
  payload: CreateRequirementPayload
): Promise<RecruitmentRequirement> {
  const res = await fetch(apiUrl(`/agent/recruitment/requirements/${id}`), {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseApiError(res, "更新招聘需求失败");
  const data: { requirement: RecruitmentRequirement } = await res.json();
  return data.requirement;
}

export async function deleteRecruitmentRequirement(id: number): Promise<void> {
  const res = await fetch(apiUrl(`/agent/recruitment/requirements/${id}`), {
    method: "DELETE",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "删除招聘需求失败");
}

export async function deleteAllRecruitmentRequirements(password: string): Promise<void> {
  const res = await fetch(apiUrl("/agent/recruitment/requirements"), {
    method: "DELETE",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw await parseApiError(res, "删除全部招聘需求失败");
}

export async function fetchRecruitmentCandidates(
  requirementId: number | null
): Promise<RecruitmentCandidate[]> {
  const suffix = requirementId ? `?requirement_id=${requirementId}` : "";
  const res = await fetch(apiUrl(`/agent/recruitment/candidates${suffix}`), {
    cache: "no-store",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "获取候选人失败");
  const data: { candidates?: RecruitmentCandidate[] } = await res.json();
  return data.candidates ?? [];
}

export async function createRecruitmentCandidate(
  payload: CreateCandidatePayload
): Promise<RecruitmentCandidate> {
  const res = await fetch(apiUrl("/agent/recruitment/candidates"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseApiError(res, "创建候选人失败");
  const data: { candidate: RecruitmentCandidate } = await res.json();
  return data.candidate;
}

export async function updateRecruitmentCandidate(
  id: number,
  payload: UpdateCandidatePayload
): Promise<RecruitmentCandidate> {
  const res = await fetch(apiUrl(`/agent/recruitment/candidates/${id}`), {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseApiError(res, "更新候选人失败");
  const data: { candidate: RecruitmentCandidate } = await res.json();
  return data.candidate;
}

export async function generateRecruitmentDraft(candidateId: number): Promise<string> {
  const res = await fetch(apiUrl(`/agent/recruitment/candidates/${candidateId}/draft`), {
    method: "POST",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "生成话术失败");
  const data: { draft?: string } = await res.json();
  return data.draft ?? "";
}

export async function generateChatDraft(input: ChatDraftInput): Promise<ChatDraftResult> {
  const res = await fetch(apiUrl("/agent/recruitment/chat-draft"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw await parseApiError(res, "生成话术失败");
  const data: ChatDraftResponse = await res.json();
  return data.result ?? { draft: "", follow_up_questions: [], scene: "follow_up" };
}

export async function runRecruitmentAgent(
  candidateId: number
): Promise<{ result: RecruitmentAgentResult; candidate: RecruitmentCandidate }> {
  const res = await fetch(apiUrl(`/agent/recruitment/candidates/${candidateId}/agent-run`), {
    method: "POST",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "运行招聘 Agent 失败");
  return res.json();
}

export async function fetchRecruitmentTimeline(candidateId: number): Promise<RecruitmentTimelineEvent[]> {
  const res = await fetch(apiUrl(`/agent/recruitment/candidates/${candidateId}/timeline`), {
    cache: "no-store",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "加载沟通时间线失败");
  const data: { events?: RecruitmentTimelineEvent[] } = await res.json();
  return data.events ?? [];
}

export async function createRecruitmentTimelineEvent(
  candidateId: number,
  payload: CreateTimelineEventPayload
): Promise<RecruitmentTimelineEvent> {
  const res = await fetch(apiUrl(`/agent/recruitment/candidates/${candidateId}/timeline`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseApiError(res, "记录沟通进展失败");
  const data: { event: RecruitmentTimelineEvent } = await res.json();
  return data.event;
}

export async function fetchBossAssistantStatus(): Promise<BossAssistantStatus> {
  const res = await fetch(apiUrl("/agent/boss-assistant/status"), {
    cache: "no-store",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "获取 BOSS 本地状态失败");
  return res.json();
}

export async function detectBossAssistant(): Promise<BossAssistantStatus> {
  const res = await fetch(apiUrl("/agent/boss-assistant/detect"), {
    method: "POST",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "检测 BOSS 网页/客户端失败");
  return res.json();
}

export async function saveBossAssistantConfig(exePath: string): Promise<BossAssistantStatus> {
  const res = await fetch(apiUrl("/agent/boss-assistant/config"), {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify({ exe_path: exePath }),
  });
  if (!res.ok) throw await parseApiError(res, "保存 BOSS 客户端路径失败");
  return res.json();
}

export async function clickBossMenu(menu: BossMenu): Promise<BossMenuClickResult> {
  const res = await fetch(apiUrl("/agent/boss-assistant/click-menu"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify({ menu }),
  });
  if (!res.ok) throw await parseApiError(res, "BOSS menu click failed");
  return res.json();
}

export async function searchBossCandidates(payload: CreateRequirementPayload): Promise<BossSearchResult> {
  const res = await fetch(apiUrl("/agent/boss-assistant/search"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseApiError(res, "BOSS candidate search failed");
  return res.json();
}

export async function importBossCandidates(requirementId: number, limit: number): Promise<BossImportCandidatesResult> {
  const res = await fetch(apiUrl("/agent/boss-assistant/import-candidates"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAgentHeaders() },
    body: JSON.stringify({ requirement_id: requirementId, limit }),
  });
  if (!res.ok) throw await parseApiError(res, "BOSS candidate import failed");
  return res.json();
}
