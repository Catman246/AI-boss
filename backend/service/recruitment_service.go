package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"sort"
	"strings"

	"github.com/2930134478/AI-CS/backend/models"
	"github.com/2930134478/AI-CS/backend/repository"
	"github.com/2930134478/AI-CS/backend/service/rag"
	"github.com/2930134478/AI-CS/backend/utils"
)

type RecruitmentService struct {
	repo             *repository.RecruitmentRepository
	agent            *RecruitmentAgentClient
	docRepo          *repository.DocumentRepository
	retrievalService *rag.RetrievalService
	aiConfigRepo     *repository.AIConfigRepository
	kbRepo           *repository.KnowledgeBaseRepository
	providerFactory  *AIProviderFactory
}

type CreateRecruitmentRequirementInput struct {
	Title                 string `json:"title"`
	Role                  string `json:"role"`
	JobCategory           string `json:"job_category"`
	Location              string `json:"location"`
	SearchKeyword         string `json:"search_keyword"`
	EducationRequirement  string `json:"education_requirement"`
	AgeRequirement        string `json:"age_requirement"`
	RecommendedFilters    string `json:"recommended_filters"`
	SortPreference        string `json:"sort_preference"`
	FilterViewed14Days    bool   `json:"filter_viewed_14_days"`
	FilterExchanged30Days bool   `json:"filter_exchanged_30_days"`
	BatchSize             int    `json:"batch_size"`
	Tags                  string `json:"tags"`
	MustHave              string `json:"must_have"`
	NiceHave              string `json:"nice_have"`
	Description           string `json:"description"`
	Status                string `json:"status"`
	OwnerID               uint   `json:"owner_id"`
}

type UpdateRecruitmentRequirementInput struct {
	ID                    uint   `json:"id"`
	Title                 string `json:"title"`
	Role                  string `json:"role"`
	JobCategory           string `json:"job_category"`
	Location              string `json:"location"`
	SearchKeyword         string `json:"search_keyword"`
	EducationRequirement  string `json:"education_requirement"`
	AgeRequirement        string `json:"age_requirement"`
	RecommendedFilters    string `json:"recommended_filters"`
	SortPreference        string `json:"sort_preference"`
	FilterViewed14Days    bool   `json:"filter_viewed_14_days"`
	FilterExchanged30Days bool   `json:"filter_exchanged_30_days"`
	BatchSize             int    `json:"batch_size"`
	Tags                  string `json:"tags"`
	MustHave              string `json:"must_have"`
	NiceHave              string `json:"nice_have"`
	Description           string `json:"description"`
	Status                string `json:"status"`
}

type CreateRecruitmentCandidateInput struct {
	RequirementID uint   `json:"requirement_id"`
	OwnerID       uint   `json:"owner_id"`
	Name          string `json:"name"`
	Source        string `json:"source"`
	CurrentRole   string `json:"current_role"`
	Location      string `json:"location"`
	Tags          string `json:"tags"`
	Profile       string `json:"profile"`
}

type UpdateRecruitmentCandidateInput struct {
	ID               uint    `json:"id"`
	Name             *string `json:"name"`
	Source           *string `json:"source"`
	CurrentRole      *string `json:"current_role"`
	Location         *string `json:"location"`
	Tags             *string `json:"tags"`
	Profile          *string `json:"profile"`
	ContactStatus    *string `json:"contact_status"`
	ConsentToContact *bool   `json:"consent_to_contact"`
	PrivateContact   *string `json:"private_contact"`
	GroupStatus      *string `json:"group_status"`
	LastMessage      *string `json:"last_message"`
	NextAction       *string `json:"next_action"`
}

type CreateRecruitmentTimelineEventInput struct {
	CandidateID uint   `json:"candidate_id"`
	OwnerID     uint   `json:"owner_id"`
	EventType   string `json:"event_type"`
	Title       string `json:"title"`
	Content     string `json:"content"`
	FromStatus  string `json:"from_status"`
	ToStatus    string `json:"to_status"`
}

// ChatDraftInput is the request payload for the chat-draft endpoint.
type ChatDraftInput struct {
	RequirementID uint          `json:"requirement_id" binding:"required"`
	CandidateID   uint          `json:"candidate_id" binding:"required"`
	Messages      []ChatMessage `json:"messages"`
	Scene         string        `json:"scene"`
}

// ChatMessage represents a single message in the recent chat history.
type ChatMessage struct {
	Role    string `json:"role"` // "recruiter" or "candidate"
	Content string `json:"content"`
}

// ChatDraftResult is the structured AI response for a chat draft.
type ChatDraftResult struct {
	Draft             string   `json:"draft"`
	FollowUpQuestions []string `json:"follow_up_questions"`
	Scene             string   `json:"scene"`
}

func NewRecruitmentService(
	repo *repository.RecruitmentRepository,
	agent *RecruitmentAgentClient,
	docRepo *repository.DocumentRepository,
	retrievalService *rag.RetrievalService,
	aiConfigRepo *repository.AIConfigRepository,
	kbRepo *repository.KnowledgeBaseRepository,
) *RecruitmentService {
	return &RecruitmentService{
		repo:             repo,
		agent:            agent,
		docRepo:          docRepo,
		retrievalService: retrievalService,
		aiConfigRepo:     aiConfigRepo,
		kbRepo:           kbRepo,
		providerFactory:  NewAIProviderFactory(),
	}
}

func (s *RecruitmentService) ListRequirements() ([]models.RecruitmentRequirement, error) {
	return s.repo.ListRequirements()
}

func (s *RecruitmentService) CreateRequirement(input CreateRecruitmentRequirementInput) (*models.RecruitmentRequirement, error) {
	item := &models.RecruitmentRequirement{
		Title:                 cleanText(input.Title),
		Role:                  cleanText(input.Role),
		JobCategory:           cleanText(input.JobCategory),
		Location:              cleanText(input.Location),
		SearchKeyword:         cleanText(input.SearchKeyword),
		EducationRequirement:  cleanText(input.EducationRequirement),
		AgeRequirement:        cleanText(input.AgeRequirement),
		RecommendedFilters:    cleanText(input.RecommendedFilters),
		SortPreference:        cleanText(input.SortPreference),
		FilterViewed14Days:    input.FilterViewed14Days,
		FilterExchanged30Days: input.FilterExchanged30Days,
		BatchSize:             normalizeBatchSize(input.BatchSize),
		Tags:                  cleanText(input.Tags),
		MustHave:              cleanText(input.MustHave),
		NiceHave:              cleanText(input.NiceHave),
		Description:           cleanText(input.Description),
		Status:                normalizeRequirementStatus(input.Status),
		OwnerID:               input.OwnerID,
	}
	if item.Title == "" || item.Role == "" {
		return nil, errors.New("title and role are required")
	}
	if err := s.repo.SaveRequirement(item); err != nil {
		return nil, err
	}
	return item, nil
}

func (s *RecruitmentService) UpdateRequirement(input UpdateRecruitmentRequirementInput) (*models.RecruitmentRequirement, error) {
	item, err := s.repo.GetRequirement(input.ID)
	if err != nil {
		return nil, err
	}
	if cleanText(input.Title) != "" {
		item.Title = cleanText(input.Title)
	}
	if cleanText(input.Role) != "" {
		item.Role = cleanText(input.Role)
	}
	item.JobCategory = cleanText(input.JobCategory)
	item.Location = cleanText(input.Location)
	item.SearchKeyword = cleanText(input.SearchKeyword)
	item.EducationRequirement = cleanText(input.EducationRequirement)
	item.AgeRequirement = cleanText(input.AgeRequirement)
	item.RecommendedFilters = cleanText(input.RecommendedFilters)
	item.SortPreference = cleanText(input.SortPreference)
	item.FilterViewed14Days = input.FilterViewed14Days
	item.FilterExchanged30Days = input.FilterExchanged30Days
	item.BatchSize = normalizeBatchSize(input.BatchSize)
	item.Tags = cleanText(input.Tags)
	item.MustHave = cleanText(input.MustHave)
	item.NiceHave = cleanText(input.NiceHave)
	item.Description = cleanText(input.Description)
	item.Status = normalizeRequirementStatus(input.Status)
	if err := s.repo.SaveRequirement(item); err != nil {
		return nil, err
	}
	return item, nil
}

func (s *RecruitmentService) DeleteRequirement(id uint) error {
	if _, err := s.repo.GetRequirement(id); err != nil {
		return err
	}
	return s.repo.DeleteRequirement(id)
}

func (s *RecruitmentService) DeleteAllRequirements() error {
	return s.repo.DeleteAllRequirements()
}

func (s *RecruitmentService) ListCandidates(requirementID uint) ([]models.RecruitmentCandidate, error) {
	return s.repo.ListCandidates(requirementID)
}

func (s *RecruitmentService) CreateCandidate(input CreateRecruitmentCandidateInput) (*models.RecruitmentCandidate, error) {
	req, err := s.repo.GetRequirement(input.RequirementID)
	if err != nil {
		return nil, err
	}
	item := &models.RecruitmentCandidate{
		RequirementID: input.RequirementID,
		OwnerID:       input.OwnerID,
		Name:          cleanText(input.Name),
		Source:        defaultString(cleanText(input.Source), "manual"),
		CurrentRole:   cleanText(input.CurrentRole),
		Location:      cleanText(input.Location),
		Tags:          cleanText(input.Tags),
		Profile:       cleanText(input.Profile),
		ContactStatus: "new",
		GroupStatus:   "not_invited",
	}
	if item.Name == "" {
		return nil, errors.New("candidate name is required")
	}
	item.MatchScore, item.MatchReason = scoreCandidate(req, item)
	if err := s.repo.SaveCandidate(item); err != nil {
		return nil, err
	}
	if err := s.addTimelineEvent(item, "candidate_created", "候选人已加入", "已加入候选人池。", "", item.ContactStatus); err != nil {
		return nil, err
	}
	return item, nil
}

func (s *RecruitmentService) UpdateCandidate(input UpdateRecruitmentCandidateInput) (*models.RecruitmentCandidate, error) {
	item, err := s.repo.GetCandidate(input.ID)
	if err != nil {
		return nil, err
	}
	oldContactStatus := item.ContactStatus
	oldGroupStatus := item.GroupStatus
	oldConsentToContact := item.ConsentToContact
	oldPrivateContact := item.PrivateContact
	oldLastMessage := item.LastMessage
	if input.Name != nil {
		item.Name = cleanText(*input.Name)
	}
	if input.Source != nil {
		item.Source = cleanText(*input.Source)
	}
	if input.CurrentRole != nil {
		item.CurrentRole = cleanText(*input.CurrentRole)
	}
	if input.Location != nil {
		item.Location = cleanText(*input.Location)
	}
	if input.Tags != nil {
		item.Tags = cleanText(*input.Tags)
	}
	if input.Profile != nil {
		item.Profile = cleanText(*input.Profile)
	}
	if input.ContactStatus != nil {
		item.ContactStatus = normalizeContactStatus(*input.ContactStatus)
	}
	if input.ConsentToContact != nil {
		item.ConsentToContact = *input.ConsentToContact
	}
	if input.PrivateContact != nil {
		item.PrivateContact = cleanText(*input.PrivateContact)
	}
	if input.GroupStatus != nil {
		item.GroupStatus = normalizeGroupStatus(*input.GroupStatus)
	}
	if input.LastMessage != nil {
		item.LastMessage = cleanText(*input.LastMessage)
	}
	if input.NextAction != nil {
		item.NextAction = cleanText(*input.NextAction)
	}
	if req, err := s.repo.GetRequirement(item.RequirementID); err == nil {
		item.MatchScore, item.MatchReason = scoreCandidate(req, item)
	}
	if err := s.repo.SaveCandidate(item); err != nil {
		return nil, err
	}
	if oldContactStatus != item.ContactStatus {
		if err := s.addTimelineEvent(item, "status_changed", "沟通状态已更新", contactStatusText(oldContactStatus)+" -> "+contactStatusText(item.ContactStatus), oldContactStatus, item.ContactStatus); err != nil {
			return nil, err
		}
	}
	if oldGroupStatus != item.GroupStatus {
		if err := s.addTimelineEvent(item, "group_changed", "私域承接状态已更新", groupStatusText(oldGroupStatus)+" -> "+groupStatusText(item.GroupStatus), oldGroupStatus, item.GroupStatus); err != nil {
			return nil, err
		}
	}
	if !oldConsentToContact && item.ConsentToContact {
		if err := s.addTimelineEvent(item, "consent_changed", "候选人已同意留资", "已记录候选人明确同意留资。", "", "consented"); err != nil {
			return nil, err
		}
	}
	if cleanText(oldPrivateContact) != cleanText(item.PrivateContact) && cleanText(item.PrivateContact) != "" {
		if err := s.addTimelineEvent(item, "contact_recorded", "已记录联系方式", "联系方式已记录，后续操作前仍需按候选人同意范围使用。", "", ""); err != nil {
			return nil, err
		}
	}
	if cleanText(oldLastMessage) != cleanText(item.LastMessage) && cleanText(item.LastMessage) != "" {
		if err := s.addTimelineEvent(item, "message_recorded", "记录候选人回复", item.LastMessage, "", item.ContactStatus); err != nil {
			return nil, err
		}
	}
	return item, nil
}

func (s *RecruitmentService) ListTimelineEvents(candidateID uint) ([]models.RecruitmentTimelineEvent, error) {
	if _, err := s.repo.GetCandidate(candidateID); err != nil {
		return nil, err
	}
	return s.repo.ListTimelineEvents(candidateID)
}

func (s *RecruitmentService) CreateTimelineEvent(input CreateRecruitmentTimelineEventInput) (*models.RecruitmentTimelineEvent, error) {
	candidate, err := s.repo.GetCandidate(input.CandidateID)
	if err != nil {
		return nil, err
	}
	eventType := normalizeTimelineEventType(input.EventType)
	item := &models.RecruitmentTimelineEvent{
		CandidateID: candidate.ID,
		OwnerID:     defaultUint(input.OwnerID, candidate.OwnerID),
		EventType:   eventType,
		Title:       defaultString(cleanText(input.Title), timelineEventTitle(eventType)),
		Content:     cleanText(input.Content),
		FromStatus:  cleanText(input.FromStatus),
		ToStatus:    cleanText(input.ToStatus),
	}
	if item.Content == "" {
		return nil, errors.New("timeline content is required")
	}
	if err := s.repo.SaveTimelineEvent(item); err != nil {
		return nil, err
	}
	return item, nil
}

func (s *RecruitmentService) GenerateDraft(ctx context.Context, candidateID uint) (string, error) {
	candidate, err := s.repo.GetCandidate(candidateID)
	if err != nil {
		return "", err
	}
	req, err := s.repo.GetRequirement(candidate.RequirementID)
	if err != nil {
		return "", err
	}
	knowledgeContext := s.loadRecruitmentKnowledge()
	if s.agent != nil && s.agent.Enabled() {
		result, err := s.agent.Run(ctx, req, candidate, knowledgeContext)
		if err == nil && strings.TrimSpace(result.Draft) != "" {
			_ = s.addTimelineEvent(candidate, "draft_generated", "生成沟通话术", result.Draft, "", candidate.ContactStatus)
			return result.Draft, nil
		}
	}
	draft := buildRecruitmentDraft(req, candidate)
	if err := s.addTimelineEvent(candidate, "draft_generated", "生成沟通话术", draft, "", candidate.ContactStatus); err != nil {
		return "", err
	}
	return draft, nil
}

func (s *RecruitmentService) RunAgent(ctx context.Context, candidateID uint) (*RecruitmentAgentRunResult, *models.RecruitmentCandidate, error) {
	candidate, err := s.repo.GetCandidate(candidateID)
	if err != nil {
		return nil, nil, err
	}
	req, err := s.repo.GetRequirement(candidate.RequirementID)
	if err != nil {
		return nil, nil, err
	}

	var result *RecruitmentAgentRunResult
	knowledgeContext := s.loadRecruitmentKnowledge()
	if s.agent != nil && s.agent.Enabled() {
		result, err = s.agent.Run(ctx, req, candidate, knowledgeContext)
		if err != nil {
			return nil, nil, err
		}
	} else {
		result = buildLocalRecruitmentAgentResult(req, candidate, knowledgeContext)
	}

	candidate.MatchScore = result.MatchScore
	candidate.MatchReason = cleanText(result.MatchReason)
	if strings.TrimSpace(result.NextAction) != "" {
		candidate.NextAction = cleanText(result.NextAction)
	}
	if err := s.repo.SaveCandidate(candidate); err != nil {
		return nil, nil, err
	}
	content := fmt.Sprintf("匹配分 %d；下一步：%s", result.MatchScore, result.NextAction)
	if err := s.addTimelineEvent(candidate, "agent_run", "Agent已运行", content, "", result.Stage); err != nil {
		return nil, nil, err
	}
	return result, candidate, nil
}

func (s *RecruitmentService) addTimelineEvent(candidate *models.RecruitmentCandidate, eventType string, title string, content string, fromStatus string, toStatus string) error {
	item := &models.RecruitmentTimelineEvent{
		CandidateID: candidate.ID,
		OwnerID:     candidate.OwnerID,
		EventType:   normalizeTimelineEventType(eventType),
		Title:       defaultString(cleanText(title), timelineEventTitle(eventType)),
		Content:     cleanText(content),
		FromStatus:  cleanText(fromStatus),
		ToStatus:    cleanText(toStatus),
	}
	return s.repo.SaveTimelineEvent(item)
}

func (s *RecruitmentService) loadRecruitmentKnowledge() string {
	if s.docRepo == nil {
		return ""
	}
	docs, err := s.docRepo.ListPublishedRAGDocs(5)
	if err != nil || len(docs) == 0 {
		return ""
	}
	var parts []string
	total := 0
	for _, doc := range docs {
		text := strings.TrimSpace(doc.Title + "\n" + doc.Content)
		if text == "" {
			continue
		}
		if len(text) > 1200 {
			text = text[:1200]
		}
		total += len(text)
		parts = append(parts, text)
		if total >= 4000 {
			break
		}
	}
	return strings.Join(parts, "\n\n---\n\n")
}

func buildLocalRecruitmentAgentResult(req *models.RecruitmentRequirement, candidate *models.RecruitmentCandidate, knowledgeContext string) *RecruitmentAgentRunResult {
	score, reason := scoreCandidate(req, candidate)
	events := []RecruitmentAgentEvent{
		{Step: "score_match", Status: "ok", Message: "Local rule-based matching completed."},
		{Step: "draft_message", Status: "ok", Message: "Local fallback draft generated."},
		{Step: "request_human_approval", Status: "pending", Message: "Human review is required before any BOSS message is sent."},
	}
	if strings.TrimSpace(knowledgeContext) != "" {
		events = append([]RecruitmentAgentEvent{
			{Step: "load_knowledge", Status: "ok", Message: "Published knowledge-base documents loaded."},
		}, events...)
	}
	return &RecruitmentAgentRunResult{
		ThreadID:              fmt.Sprintf("candidate-%d", candidate.ID),
		Stage:                 "awaiting_human_approval",
		MatchScore:            score,
		MatchReason:           reason,
		Draft:                 buildRecruitmentDraft(req, candidate),
		NextAction:            withKnowledgeHint(nextRecruitmentAction(candidate), knowledgeContext),
		RequiresHumanApproval: true,
		Mode:                  "local",
		Events:                events,
	}
}

func buildRecruitmentDraft(req *models.RecruitmentRequirement, candidate *models.RecruitmentCandidate) string {
	role := defaultString(req.Role, req.Title)
	location := req.Location
	if location == "" {
		location = "本地"
	}
	reason := candidate.MatchReason
	if reason == "" {
		reason = "经历与岗位要求有匹配点"
	}
	name := candidate.Name
	if name == "" {
		name = "你好"
	}
	return name + "，你好。我这边有一个" + location + "的" + role + "机会，看到你的资料里" + reason + "，想先确认你近期是否考虑相关工作机会？如果你愿意，我们可以先在平台内沟通岗位内容；后续需要记录联系方式或邀请进群时，会先征得你的明确同意。"
}

func nextRecruitmentAction(candidate *models.RecruitmentCandidate) string {
	if candidate.ConsentToContact && strings.TrimSpace(candidate.PrivateContact) != "" {
		return "核对联系方式，并确认候选人是否愿意加入微信群或企业微信。"
	}
	switch candidate.ContactStatus {
	case "replied":
		return "根据候选人回复继续沟通岗位细节；未明确同意前不记录私人联系方式。"
	case "contacted":
		return "等待候选人回复；如长期未回复，由人工判断是否停止跟进。"
	default:
		return "人工确认首轮话术后，在 BOSS 平台内发送。"
	}
}

func withKnowledgeHint(action string, knowledgeContext string) string {
	hint := strings.TrimSpace(strings.Split(strings.TrimSpace(knowledgeContext), "\n")[0])
	if hint == "" {
		return action
	}
	if len(hint) > 160 {
		hint = hint[:160] + "..."
	}
	return action + "\nKnowledge hint: " + hint
}

func scoreCandidate(req *models.RecruitmentRequirement, candidate *models.RecruitmentCandidate) (int, string) {
	haystack := normalizeForMatch(strings.Join([]string{
		candidate.Name,
		candidate.CurrentRole,
		candidate.Location,
		candidate.Tags,
		candidate.Profile,
	}, " "))
	score := 0
	reasons := []string{}

	roleTokens := tokens(req.Role)
	for _, token := range roleTokens {
		if containsToken(haystack, token) {
			score += 30
			reasons = append(reasons, "岗位关键词匹配: "+token)
			break
		}
	}
	if req.Location != "" && containsToken(haystack, req.Location) {
		score += 15
		reasons = append(reasons, "地点匹配: "+req.Location)
	}
	score += weightedTokenScore(haystack, req.MustHave, 12, 35, &reasons, "硬性条件")
	score += weightedTokenScore(haystack, req.NiceHave, 6, 18, &reasons, "加分条件")
	score += weightedTokenScore(haystack, req.Tags, 8, 24, &reasons, "标签")
	if score > 100 {
		score = 100
	}
	if len(reasons) == 0 {
		reasons = append(reasons, "需要人工复核")
	}
	sort.Strings(reasons)
	return score, strings.Join(reasons, "；")
}

func weightedTokenScore(haystack string, raw string, perHit int, maxScore int, reasons *[]string, label string) int {
	total := 0
	for _, token := range tokens(raw) {
		if containsToken(haystack, token) {
			total += perHit
			*reasons = append(*reasons, label+"匹配: "+token)
		}
		if total >= maxScore {
			return maxScore
		}
	}
	return total
}

func tokens(raw string) []string {
	parts := strings.FieldsFunc(raw, func(r rune) bool {
		return r == ',' || r == '，' || r == ';' || r == '；' || r == '/' || r == '、' || r == '\n' || r == '\t' || r == ' '
	})
	out := make([]string, 0, len(parts))
	seen := map[string]bool{}
	for _, part := range parts {
		token := cleanText(part)
		if token == "" {
			continue
		}
		key := normalizeForMatch(token)
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, token)
	}
	return out
}

func containsToken(haystack string, token string) bool {
	token = normalizeForMatch(token)
	return token != "" && strings.Contains(haystack, token)
}

func normalizeForMatch(raw string) string {
	return strings.ToLower(strings.TrimSpace(raw))
}

func cleanText(raw string) string {
	return strings.TrimSpace(raw)
}

func defaultString(value string, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func defaultUint(value uint, fallback uint) uint {
	if value == 0 {
		return fallback
	}
	return value
}

func normalizeBatchSize(value int) int {
	if value <= 0 {
		return 10
	}
	if value > 50 {
		return 50
	}
	return value
}

func normalizeRequirementStatus(value string) string {
	switch strings.TrimSpace(value) {
	case "paused", "closed":
		return strings.TrimSpace(value)
	default:
		return "active"
	}
}

func normalizeTimelineEventType(value string) string {
	switch strings.TrimSpace(value) {
	case "candidate_created", "agent_run", "draft_generated", "status_changed", "group_changed", "message_recorded", "consent_changed", "contact_recorded":
		return strings.TrimSpace(value)
	default:
		return "manual_note"
	}
}

func timelineEventTitle(eventType string) string {
	switch normalizeTimelineEventType(eventType) {
	case "candidate_created":
		return "候选人已加入"
	case "agent_run":
		return "Agent已运行"
	case "draft_generated":
		return "生成沟通话术"
	case "status_changed":
		return "沟通状态已更新"
	case "group_changed":
		return "私域承接状态已更新"
	case "message_recorded":
		return "记录候选人回复"
	case "consent_changed":
		return "候选人已同意留资"
	case "contact_recorded":
		return "已记录联系方式"
	default:
		return "人工记录"
	}
}

func contactStatusText(value string) string {
	switch normalizeContactStatus(value) {
	case "contacted":
		return "已沟通"
	case "replied":
		return "已回复"
	case "consented":
		return "已同意留资"
	case "group_invited":
		return "已邀入群"
	case "rejected":
		return "不合适"
	default:
		return "待筛选"
	}
}

func groupStatusText(value string) string {
	switch normalizeGroupStatus(value) {
	case "invited":
		return "已邀请"
	case "joined":
		return "已入群"
	case "not_joined":
		return "未入群"
	default:
		return "未邀请"
	}
}

func normalizeContactStatus(value string) string {
	switch strings.TrimSpace(value) {
	case "contacted", "replied", "consented", "group_invited", "rejected":
		return strings.TrimSpace(value)
	default:
		return "new"
	}
}

func normalizeGroupStatus(value string) string {
	switch strings.TrimSpace(value) {
	case "invited", "joined", "not_joined":
		return strings.TrimSpace(value)
	default:
		return "not_invited"
	}
}

// ──────────────────────────────────────────────────────────────────
// Chat Draft API — RAG + LLM 生成招聘聊天话术
// ──────────────────────────────────────────────────────────────────

// GenerateChatDraft generates an AI-powered recruitment chat draft using RAG + LLM.
func (s *RecruitmentService) GenerateChatDraft(ctx context.Context, userID uint, input ChatDraftInput) (*ChatDraftResult, error) {
	// 1. Load requirement + candidate
	req, err := s.repo.GetRequirement(input.RequirementID)
	if err != nil {
		return nil, fmt.Errorf("requirement not found: %w", err)
	}
	candidate, err := s.repo.GetCandidate(input.CandidateID)
	if err != nil {
		return nil, fmt.Errorf("candidate not found: %w", err)
	}

	// Security: verify the user owns both the requirement and candidate
	if req.OwnerID != userID {
		return nil, fmt.Errorf("permission denied: requirement does not belong to user")
	}
	if candidate.OwnerID != userID {
		return nil, fmt.Errorf("permission denied: candidate does not belong to user")
	}

	// 2. RAG retrieval against recruitment talk script KB
	ragContext := ""
	if s.retrievalService != nil {
		ragQuery := buildChatDraftRAGQuery(req, candidate, input.Messages)
		kbID := s.findRecruitmentKnowledgeBaseID()
		results, ragErr := s.retrievalService.RetrieveWithRerank(ctx, ragQuery, 5, kbID)
		if ragErr != nil {
			log.Printf("[chat-draft] RAG retrieval failed: %v", ragErr)
		} else if len(results) > 0 {
			ragContext = formatRAGResults(results)
		}
	}

	// 3. Load AI config
	aiConfig, err := s.aiConfigRepo.GetActiveByUserID(userID, "text")
	if err != nil {
		return nil, fmt.Errorf("no active AI text config found for user %d: %w", userID, err)
	}
	apiKey, err := utils.DecryptAPIKey(aiConfig.APIKey)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt API key: %w", err)
	}

	// 4. Build recruitment-specific prompt
	systemPrompt := buildChatDraftSystemPrompt(req, candidate, ragContext, input.Scene, input.Messages)

	// 5. Call LLM
	provider, err := s.providerFactory.CreateProvider(AIConfig{
		APIURL:    aiConfig.APIURL,
		APIKey:    apiKey,
		Model:     aiConfig.Model,
		ModelType: aiConfig.ModelType,
		Provider:  aiConfig.Provider,
	})
	if err != nil {
		log.Printf("[chat-draft] create provider failed: %v", err)
		return s.chatDraftFallback(req, candidate), nil
	}

	llmResponse, err := provider.GenerateResponse([]MessageHistory{{Role: "system", Content: systemPrompt}}, "请根据以上信息生成回复草稿", "", "")
	if err != nil {
		log.Printf("[chat-draft] LLM call failed: %v", err)
		return s.chatDraftFallback(req, candidate), nil
	}

	// 6. Parse structured result
	result, err := parseChatDraftResponse(llmResponse)
	if err != nil {
		log.Printf("[chat-draft] failed to parse LLM response: %v, raw=%s", err, llmResponse)
		return s.chatDraftFallback(req, candidate), nil
	}

	// 7. Record timeline event
	if candidate.ID != 0 {
		_ = s.addTimelineEvent(candidate, "draft_generated", "AI生成聊天话术",
			fmt.Sprintf("场景: %s\n话术: %s", result.Scene, result.Draft),
			"", candidate.ContactStatus)
	}

	return result, nil
}

// findRecruitmentKnowledgeBaseID locates the "招聘客服话术" KB by name.
func (s *RecruitmentService) findRecruitmentKnowledgeBaseID() *uint {
	if s.kbRepo == nil {
		return nil
	}
	kbs, err := s.kbRepo.List()
	if err != nil {
		return nil
	}
	for i := range kbs {
		if kbs[i].Name == "招聘客服话术" {
			id := kbs[i].ID
			return &id
		}
	}
	return nil
}

// buildChatDraftRAGQuery constructs the RAG search query from context.
func buildChatDraftRAGQuery(req *models.RecruitmentRequirement, candidate *models.RecruitmentCandidate, messages []ChatMessage) string {
	parts := []string{}
	if req.Role != "" {
		parts = append(parts, "岗位: "+req.Role)
	}
	if candidate.CurrentRole != "" {
		parts = append(parts, "候选人当前职位: "+candidate.CurrentRole)
	}
	for i := len(messages) - 1; i >= 0; i-- {
		if messages[i].Role == "candidate" {
			parts = append(parts, "候选人最近消息: "+messages[i].Content)
			break
		}
	}
	if len(parts) == 0 {
		parts = append(parts, "招聘沟通话术")
	}
	return strings.Join(parts, "; ")
}

// formatRAGResults converts RAG results to prompt context string.
func formatRAGResults(results []rag.SearchResult) string {
	var parts []string
	for i, r := range results {
		if i >= 5 {
			break
		}
		parts = append(parts, fmt.Sprintf("话术 %d:\n%s", i+1, r.Content))
	}
	return strings.Join(parts, "\n\n")
}

// buildChatDraftSystemPrompt builds the recruitment-specific LLM prompt.
func buildChatDraftSystemPrompt(req *models.RecruitmentRequirement, candidate *models.RecruitmentCandidate, ragContext string, scene string, messages []ChatMessage) string {
	var b strings.Builder
	b.WriteString("你是蓝领招聘客服助手，沟通对象多为学历不高的求职者（初中及以下）。请根据以下信息，生成一条可直接发送给候选人的中文回复草稿。\n\n")

	// Communication style — optimized for blue-collar recruitment
	b.WriteString("## 沟通风格（请遵守）\n")
	b.WriteString("1. 口语化、像微信聊天，不要书面语，不要用「您」「先生/女士」等过度尊称，直接用「你」；\n")
	b.WriteString("2. 开头直奔主题，禁止铺垫（如「了解到你之前做过XX」「这可能为你积累了经验」）；\n")
	b.WriteString("3. 短句优先，每句话不超过 15~20 字，整条回复控制在 2~3 句话、60~120 字左右；\n")
	b.WriteString("4. 一次只说一件事，不要一口气问多个问题（追问建议单独放在 follow_up_questions 里）；\n")
	b.WriteString("5. 用简单词汇，避免「适配度」「相关经验积累」「进一步沟通」等书面表达，改成「合适」「做过类似的」「聊聊」；\n")
	b.WriteString("6. 不要重复候选人已知信息（如候选人说了自己的经历，不要再复述一遍）。\n\n")

	// Behavior constraints (Kimi model guidelines)
	b.WriteString("## 行为准则（必须严格遵守）\n")
	b.WriteString("1. 禁止承诺或暗示虚假的薪资待遇、福利条件；\n")
	b.WriteString("2. 禁止直接索要候选人的身份证号、银行卡号、家庭住址等个人隐私信息；\n")
	b.WriteString("3. 发起任何沟通或邀约前，必须先确认候选人的意愿，不得强行推进；\n")
	b.WriteString("4. 你生成的所有内容均为草稿，默认需要人工审核后才能发送给候选人，因此回复中不要出现「已发送」「请查收」等暗示消息已发出的表述。\n\n")

	// Common scenario handling rules
	b.WriteString("## 常见场景处理指引\n")
	b.WriteString("- 候选人说「没经验」「没做过」→ 追问学习意愿（「愿意学吗？」）或相近经历（「做过类似的活吗？」），不要直接放弃或长篇鼓励；\n")
	b.WriteString("- 候选人问「工资多少」「多少钱一个月」→ 结合招聘需求中的岗位信息给出范围说明（如「普工 5000~6000」「计件多劳多得」），只描述不承诺，不能说「保证你能拿多少」；\n")
	b.WriteString("- 候选人问「在哪里」「远不远」→ 直接给出地点，问一句「方便过来吗？」即可，不要展开介绍公司；\n")
	b.WriteString("- 候选人已读不回超过一轮 → 简单追问一句「还在找工作吗？」即可，不要连续发多条。\n\n")

	// Scene constraint
	sceneLabel := sceneLabelText(scene)
	if sceneLabel != "" {
		b.WriteString(fmt.Sprintf("## 目标场景：%s\n", sceneLabel))
		b.WriteString("请围绕此场景生成对应的回复风格。\n\n")
	}

	// Requirement context
	b.WriteString("## 招聘需求\n")
	b.WriteString(fmt.Sprintf("- 岗位: %s\n", defaultString(req.Role, req.Title)))
	if req.Location != "" {
		b.WriteString(fmt.Sprintf("- 地点: %s\n", req.Location))
	}
	if req.MustHave != "" {
		b.WriteString(fmt.Sprintf("- 硬性要求: %s\n", req.MustHave))
	}
	if req.NiceHave != "" {
		b.WriteString(fmt.Sprintf("- 加分条件: %s\n", req.NiceHave))
	}
	if req.Description != "" {
		b.WriteString(fmt.Sprintf("- 岗位描述: %s\n", req.Description))
	}

	// Candidate context
	b.WriteString("\n## 候选人信息\n")
	if candidate.Name != "" {
		b.WriteString(fmt.Sprintf("- 姓名: %s\n", candidate.Name))
	}
	if candidate.CurrentRole != "" {
		b.WriteString(fmt.Sprintf("- 当前职位: %s\n", candidate.CurrentRole))
	}
	if candidate.Location != "" {
		b.WriteString(fmt.Sprintf("- 所在地: %s\n", candidate.Location))
	}
	if candidate.Profile != "" {
		b.WriteString(fmt.Sprintf("- 个人简介: %s\n", candidate.Profile))
	}
	b.WriteString(fmt.Sprintf("- 沟通状态: %s\n", contactStatusText(candidate.ContactStatus)))

	// Chat history
	if len(messages) > 0 {
		b.WriteString("\n## 最近聊天记录\n")
		for _, msg := range messages {
			roleLabel := "招聘方"
			if msg.Role == "candidate" {
				roleLabel = "候选人"
			}
			b.WriteString(fmt.Sprintf("- [%s] %s\n", roleLabel, msg.Content))
		}
	}

	// RAG knowledge
	if ragContext != "" {
		b.WriteString("\n## 参考话术（来自知识库）\n")
		b.WriteString(ragContext)
		b.WriteString("\n")
	}

	// Output format instruction
	b.WriteString("\n## 输出要求\n")
	b.WriteString("请以JSON格式输出，包含以下字段:\n")
	b.WriteString("- draft: 可直接发送的中文回复草稿。要求：口语化短句、无客套铺垫、2~3句话、总字数 60~120 字、像真人微信聊天；禁止使用 Markdown\n")
	b.WriteString("- follow_up_questions: 建议的1-3个后续追问（用于推进了解岗位意向、工期、经验、地区等）\n")
	b.WriteString("- scene: 场景分类，从以下选择: greeting(初次打招呼), follow_up(跟进), interview_invite(邀约面试), info_request(索要信息), objection_handling(异议处理), closing(收尾/加微信)\n\n")
	b.WriteString("只输出JSON，不要包含其他内容。\n")
	b.WriteString("{\n  \"draft\": \"...\",\n  \"follow_up_questions\": [\"...\"],\n  \"scene\": \"...\"\n}")

	return b.String()
}

// parseChatDraftResponse extracts structured output from LLM text.
// sceneLabelText maps scene codes to Chinese labels for prompt guidance.
func sceneLabelText(scene string) string {
	switch scene {
	case "greeting":
		return "初次打招呼 —语气自然简短，确认候选人在找工作和所在地"
	case "follow_up":
		return "跟进 — 推进了解岗位意向、工期、经验、地区等"
	case "interview_invite":
		return "邀约面试/到场 — 收集可面试时间，说明地址和联系人确认后发送"
	case "info_request":
		return "索要信息 — 确认年龄、学历、到岗时间等必要信息"
	case "objection_handling":
		return "异议处理 — 候选人对薪资/距离/靠谱性有疑虑时，礼貌回应降低顾虑"
	case "closing":
		return "收尾/加微信 — 确认意向后引导交换微信或结束沟通"
	default:
		return ""
	}
}

func parseChatDraftResponse(raw string) (*ChatDraftResult, error) {
	raw = strings.TrimSpace(raw)
	// Strip markdown code fences if present
	if strings.HasPrefix(raw, "```") {
		raw = strings.TrimPrefix(raw, "```json")
		raw = strings.TrimPrefix(raw, "```")
		raw = strings.TrimSuffix(raw, "```")
		raw = strings.TrimSpace(raw)
	}
	var result ChatDraftResult
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	if strings.TrimSpace(result.Draft) == "" {
		return nil, fmt.Errorf("draft is empty")
	}
	if result.Scene == "" {
		result.Scene = "follow_up"
	}
	return &result, nil
}

// chatDraftFallback returns a template-based draft when LLM is unavailable.
func (s *RecruitmentService) chatDraftFallback(req *models.RecruitmentRequirement, candidate *models.RecruitmentCandidate) *ChatDraftResult {
	draft := buildRecruitmentDraft(req, candidate)
	return &ChatDraftResult{
		Draft:             draft,
		FollowUpQuestions: []string{"请问你近期是否考虑相关工作机会？"},
		Scene:             "greeting",
	}
}
