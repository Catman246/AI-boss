package controller

import (
	"net/http"

	"github.com/2930134478/AI-CS/backend/service"
	"github.com/gin-gonic/gin"
)

type RecruitmentController struct {
	service *service.RecruitmentService
	users   *service.UserService
}

func NewRecruitmentController(s *service.RecruitmentService, users *service.UserService) *RecruitmentController {
	return &RecruitmentController{service: s, users: users}
}

func (r *RecruitmentController) ListRequirements(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	list, err := r.service.ListRequirements()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"requirements": list})
}

func (r *RecruitmentController) CreateRequirement(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	var req service.CreateRecruitmentRequirementInput
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}
	req.OwnerID = getUserIDFromHeader(c)
	item, err := r.service.CreateRequirement(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"requirement": item})
}

func (r *RecruitmentController) UpdateRequirement(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	id, err := parseUintParam(c, "id")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid requirement id"})
		return
	}
	var req service.UpdateRecruitmentRequirementInput
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}
	req.ID = uint(id)
	item, err := r.service.UpdateRequirement(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"requirement": item})
}

func (r *RecruitmentController) DeleteRequirement(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	id, err := parseUintParam(c, "id")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid requirement id"})
		return
	}
	if err := r.service.DeleteRequirement(uint(id)); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ok": true})
}

func (r *RecruitmentController) DeleteAllRequirements(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	var req struct {
		Password string `json:"password"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}
	if err := r.users.VerifyPassword(getUserIDFromHeader(c), req.Password); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if err := r.service.DeleteAllRequirements(); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ok": true})
}

func (r *RecruitmentController) ListCandidates(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	var requirementID uint
	if raw := c.Query("requirement_id"); raw != "" {
		parsed, err := parseUintQuery(c, "requirement_id")
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid requirement id"})
			return
		}
		requirementID = uint(parsed)
	}
	list, err := r.service.ListCandidates(requirementID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"candidates": list})
}

func (r *RecruitmentController) CreateCandidate(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	var req service.CreateRecruitmentCandidateInput
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}
	req.OwnerID = getUserIDFromHeader(c)
	item, err := r.service.CreateCandidate(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"candidate": item})
}

func (r *RecruitmentController) UpdateCandidate(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	id, err := parseUintParam(c, "id")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid candidate id"})
		return
	}
	var req service.UpdateRecruitmentCandidateInput
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}
	req.ID = uint(id)
	item, err := r.service.UpdateCandidate(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"candidate": item})
}

func (r *RecruitmentController) GenerateDraft(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	id, err := parseUintParam(c, "id")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid candidate id"})
		return
	}
	draft, err := r.service.GenerateDraft(c.Request.Context(), uint(id))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"draft": draft})
}

// ChatDraft generates an AI-powered chat draft using RAG + LLM.
// POST /agent/recruitment/chat-draft
func (r *RecruitmentController) ChatDraft(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	var input service.ChatDraftInput
	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request: " + err.Error()})
		return
	}
	userID := getUserIDFromHeader(c)
	result, err := r.service.GenerateChatDraft(c.Request.Context(), userID, input)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"result": result})
}

func (r *RecruitmentController) ListTimelineEvents(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	id, err := parseUintParam(c, "id")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid candidate id"})
		return
	}
	events, err := r.service.ListTimelineEvents(uint(id))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"events": events})
}

func (r *RecruitmentController) CreateTimelineEvent(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	id, err := parseUintParam(c, "id")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid candidate id"})
		return
	}
	var req service.CreateRecruitmentTimelineEventInput
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}
	req.CandidateID = uint(id)
	req.OwnerID = getUserIDFromHeader(c)
	event, err := r.service.CreateTimelineEvent(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"event": event})
}

func (r *RecruitmentController) RunAgent(c *gin.Context) {
	if !requirePermission(c, r.users, string(service.PermRecruitment)) {
		return
	}
	id, err := parseUintParam(c, "id")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid candidate id"})
		return
	}
	result, candidate, err := r.service.RunAgent(c.Request.Context(), uint(id))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"result": result, "candidate": candidate})
}
