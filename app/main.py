from __future__ import annotations

import hmac
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ai import DraftService
from .boss import BossError
from .knowledge import KnowledgeStore
from .recruiting import RecruitingStore
from .greetings import GreetingScheduler, GreetingStore, PlanConflictError


AUTH_COOKIE = "boss_chat_session"
STATIC_DIR = Path(__file__).with_name("static")
PROJECT_DIR = Path(__file__).parents[1]
DATA_DIR = PROJECT_DIR / "data"


class LoginRequest(BaseModel):
    username: str
    password: str


class MessageRequest(BaseModel):
    text: str


class DraftRequest(BaseModel):
    force: bool = False


class CandidateRequest(BaseModel):
    name: str
    job: str = ""
    wechat_id: str = ""


class CandidateUpdate(BaseModel):
    name: str | None = None
    job: str | None = None
    wechat_id: str | None = None
    private_contact: str | None = None
    stage: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class ChannelMessageRequest(BaseModel):
    channel: str
    sender: str
    text: str


class CandidateDraftRequest(BaseModel):
    channel: str
    force: bool = False


class InterviewRequest(BaseModel):
    starts_at: str
    location: str


class TaskSendRequest(BaseModel):
    text: str | None = None


class GreetingPlanRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    daily_limit: int | None = None
    hourly_limit: int | None = None
    start_at: str | None = None
    end_at: str | None = None


class KnowledgeRequest(BaseModel):
    title: str
    content: str
    keywords: str = ""
    enabled: bool = True


class KnowledgeUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    keywords: str | None = None
    enabled: bool | None = None


class AIConfigRequest(BaseModel):
    provider: str
    base_url: str
    api_key: str = ""
    model: str


def create_app(
    boss: Any | None = None,
    knowledge: Any | None = None,
    drafts: Any | None = None,
    recruiting: Any | None = None,
    greetings: Any | None = None,
    data_dir: Path | None = None,
    seed_dir: Path | None = None,
) -> FastAPI:
    runtime_data = Path(data_dir) if data_dir is not None else DATA_DIR
    resources = Path(seed_dir) if seed_dir is not None else DATA_DIR
    if boss is None:
        from .boss import BossAdapter

        boss = BossAdapter()

    if knowledge is None:
        from .semantic import SemanticIndex

        semantic = SemanticIndex(
            runtime_data / "lancedb", runtime_data / "models" / "fastembed"
        )
        knowledge = KnowledgeStore(runtime_data / "knowledge.db", semantic=semantic)
        for seed in (
            resources / "recruitment-talk-script-seed.md",
            resources / "recruitment-safety-seed.md",
        ):
            if seed.exists():
                knowledge.seed_markdown(seed)
        knowledge.reindex()
    if drafts is None:
        config_path = PROJECT_DIR / ".env" if data_dir is None else runtime_data / "ai.env"
        drafts = DraftService(knowledge, config_path=config_path)
    if recruiting is None:
        recruiting = RecruitingStore(runtime_data / "recruiting.db")
    if greetings is None:
        greetings = GreetingScheduler(
            GreetingStore(runtime_data / "greetings.db"), boss
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        start = getattr(greetings, "start", None)
        stop = getattr(greetings, "stop", None)
        if start:
            start()
        try:
            yield
        finally:
            if stop:
                stop()

    app = FastAPI(
        title="BOSS Chat Local", docs_url=None, redoc_url=None, lifespan=lifespan
    )

    app.state.boss = boss
    app.state.knowledge = knowledge
    app.state.drafts = drafts
    app.state.recruiting = recruiting
    app.state.greetings = greetings
    app.state.session_token = secrets.token_urlsafe(32)

    @app.exception_handler(BossError)
    async def boss_error_handler(_request: Request, exc: BossError) -> JSONResponse:
        return JSONResponse(
            status_code=502, content={"detail": str(exc), "code": exc.code}
        )

    def require_session(request: Request) -> None:
        supplied = request.cookies.get(AUTH_COOKIE, "")
        if not hmac.compare_digest(supplied, app.state.session_token):
            raise HTTPException(status_code=401, detail="请先登录")

    @app.post("/api/login")
    def login(payload: LoginRequest, response: Response) -> dict[str, bool]:
        valid_user = hmac.compare_digest(payload.username, "admin")
        valid_password = hmac.compare_digest(payload.password, "123456")
        if not (valid_user and valid_password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        response.set_cookie(
            AUTH_COOKIE,
            app.state.session_token,
            httponly=True,
            samesite="strict",
            secure=False,
        )
        return {"authenticated": True}

    @app.post("/api/logout", dependencies=[Depends(require_session)])
    def logout(response: Response) -> dict[str, bool]:
        response.delete_cookie(AUTH_COOKIE, samesite="strict")
        return {"authenticated": False}

    @app.get("/api/me", dependencies=[Depends(require_session)])
    def me() -> dict[str, Any]:
        return {"authenticated": True, "username": "admin"}

    @app.get("/api/status", dependencies=[Depends(require_session)])
    def status() -> dict[str, Any]:
        return app.state.boss.status()

    @app.post("/api/boss/view/{view}", dependencies=[Depends(require_session)])
    def open_boss_view(view: str) -> dict[str, str]:
        if view not in {"chat", "recommend"}:
            raise HTTPException(status_code=422, detail="BOSS 页面只能切换到 chat 或 recommend")
        try:
            return app.state.boss.open_view(view, activate=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/ai/status", dependencies=[Depends(require_session)])
    def ai_status() -> dict[str, Any]:
        return app.state.drafts.status()

    @app.get("/api/ai/config", dependencies=[Depends(require_session)])
    def ai_config() -> dict[str, Any]:
        return app.state.drafts.config()

    @app.put("/api/ai/config", dependencies=[Depends(require_session)])
    def save_ai_config(payload: AIConfigRequest) -> dict[str, Any]:
        try:
            return app.state.drafts.save_config(
                payload.provider, payload.base_url, payload.api_key, payload.model
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/ai/config/test", dependencies=[Depends(require_session)])
    def test_ai_config(payload: AIConfigRequest) -> dict[str, Any]:
        try:
            return app.state.drafts.test_config(
                payload.provider, payload.base_url, payload.api_key, payload.model
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"连接测试失败：{exc}") from exc

    @app.get("/api/contacts", dependencies=[Depends(require_session)])
    def contacts(passive: bool = True) -> list[dict[str, Any]]:
        return app.state.boss.contacts(passive=passive)

    @app.get("/api/contacts/{key}/messages", dependencies=[Depends(require_session)])
    def messages(key: str, passive: bool = True) -> dict[str, Any]:
        return app.state.boss.messages(key, passive=passive)

    @app.post("/api/contacts/{key}/messages", dependencies=[Depends(require_session)])
    def send_message(key: str, payload: MessageRequest) -> dict[str, Any]:
        text = payload.text.strip()
        if not text or len(text) > 2000:
            raise HTTPException(status_code=422, detail="消息长度必须为 1 到 2000 个字符")
        return app.state.boss.send(key, text)

    @app.post("/api/contacts/{key}/draft", dependencies=[Depends(require_session)])
    def create_draft(key: str, payload: DraftRequest) -> dict[str, Any]:
        conversation = app.state.boss.messages(key, passive=True)
        return app.state.drafts.generate(
            key,
            conversation["contact"].get("job", ""),
            conversation["messages"],
            force=payload.force,
        )

    @app.get("/api/knowledge", dependencies=[Depends(require_session)])
    def list_knowledge() -> list[dict[str, Any]]:
        return app.state.knowledge.list_entries()

    @app.get("/api/knowledge/status", dependencies=[Depends(require_session)])
    def knowledge_status() -> dict[str, Any]:
        status_method = getattr(app.state.knowledge, "semantic_status", None)
        return status_method() if status_method else {"configured": False, "ready": False, "error": ""}

    @app.post("/api/knowledge", dependencies=[Depends(require_session)])
    def create_knowledge(payload: KnowledgeRequest) -> dict[str, Any]:
        title = payload.title.strip()
        content = payload.content.strip()
        if not title or not content:
            raise HTTPException(status_code=422, detail="知识标题和内容不能为空")
        try:
            return app.state.knowledge.create_entry(
                title,
                content,
                payload.keywords.strip(),
                payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="知识标题已存在") from exc

    @app.patch("/api/knowledge/{entry_id}", dependencies=[Depends(require_session)])
    def update_knowledge(
        entry_id: int, payload: KnowledgeUpdate
    ) -> dict[str, Any]:
        changes = payload.model_dump(exclude_unset=True)
        for field in ("title", "content", "keywords"):
            if field in changes and changes[field] is not None:
                changes[field] = changes[field].strip()
        try:
            return app.state.knowledge.update_entry(entry_id, **changes)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="知识条目不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="知识标题已存在") from exc

    @app.delete("/api/knowledge/{entry_id}", dependencies=[Depends(require_session)])
    def delete_knowledge(entry_id: int) -> dict[str, bool]:
        try:
            app.state.knowledge.delete_entry(entry_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="知识条目不存在") from exc
        return {"deleted": True}

    @app.get("/api/candidates", dependencies=[Depends(require_session)])
    def list_candidates(channel: str | None = None, refresh: bool = True) -> list[dict[str, Any]]:
        if refresh and channel in {None, "boss"}:
            try:
                app.state.recruiting.sync_boss_contacts(
                    app.state.boss.contacts(passive=True)
                )
            except BossError:
                pass
        return app.state.recruiting.list_candidates(channel=channel)

    @app.post("/api/candidates", dependencies=[Depends(require_session)])
    def create_candidate(payload: CandidateRequest) -> dict[str, Any]:
        try:
            return app.state.recruiting.create_candidate(
                payload.name, payload.job, payload.wechat_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/candidates/{candidate_id}", dependencies=[Depends(require_session)])
    def get_candidate(candidate_id: int) -> dict[str, Any]:
        candidate = app.state.recruiting.get_candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="候选人不存在")
        return candidate

    @app.patch("/api/candidates/{candidate_id}", dependencies=[Depends(require_session)])
    def update_candidate(candidate_id: int, payload: CandidateUpdate) -> dict[str, Any]:
        try:
            return app.state.recruiting.update_candidate(
                candidate_id, **payload.model_dump(exclude_unset=True)
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="候选人不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete(
        "/api/candidates/{candidate_id}/boss-conversation",
        dependencies=[Depends(require_session)],
    )
    def delete_boss_conversation(candidate_id: int) -> dict[str, bool]:
        candidate = app.state.recruiting.get_candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="候选人不存在")
        if not candidate.get("boss_key"):
            raise HTTPException(status_code=409, detail="候选人没有 BOSS 会话")

        app.state.boss.delete_contact(candidate["boss_key"])
        app.state.recruiting.detach_boss_contact(candidate_id)
        return {"deleted": True}

    @app.get("/api/candidates/{candidate_id}/messages", dependencies=[Depends(require_session)])
    def candidate_messages(
        candidate_id: int, channel: str, activate: bool = False
    ) -> list[dict[str, Any]]:
        candidate = app.state.recruiting.get_candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="候选人不存在")
        if channel == "boss" and candidate.get("boss_key"):
            conversation = app.state.boss.messages(
                candidate["boss_key"], passive=not activate
            )
            return conversation["messages"]
        try:
            return app.state.recruiting.list_messages(candidate_id, channel)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/candidates/{candidate_id}/messages", dependencies=[Depends(require_session)])
    def add_candidate_message(
        candidate_id: int, payload: ChannelMessageRequest
    ) -> dict[str, Any]:
        try:
            return app.state.recruiting.add_message(
                candidate_id, payload.channel, payload.sender, payload.text
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="候选人不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/candidates/{candidate_id}/draft", dependencies=[Depends(require_session)])
    def create_candidate_draft(
        candidate_id: int, payload: CandidateDraftRequest
    ) -> dict[str, Any]:
        candidate = app.state.recruiting.get_candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="候选人不存在")
        if payload.channel == "boss" and candidate.get("boss_key"):
            messages = app.state.boss.messages(candidate["boss_key"], passive=True)["messages"]
        else:
            try:
                local_messages = app.state.recruiting.list_messages(candidate_id, payload.channel)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            messages = [
                {
                    **message,
                    "sender": "contact" if message["sender"] == "candidate" else "me",
                    "time": message.get("created_at", ""),
                }
                for message in local_messages
            ]
        return app.state.drafts.generate(
            f"{payload.channel}:{candidate_id}",
            candidate.get("job", ""),
            messages,
            force=payload.force,
            agent=payload.channel,
        )

    @app.post("/api/candidates/{candidate_id}/interviews", dependencies=[Depends(require_session)])
    def schedule_interview(candidate_id: int, payload: InterviewRequest) -> dict[str, Any]:
        try:
            return app.state.recruiting.schedule_interview(
                candidate_id, payload.starts_at, payload.location
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="候选人不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/tasks", dependencies=[Depends(require_session)])
    def list_tasks(status: str | None = None) -> list[dict[str, Any]]:
        return app.state.recruiting.list_tasks(status=status)

    @app.post("/api/tasks/{task_id}/send", dependencies=[Depends(require_session)])
    def send_task(task_id: int, payload: TaskSendRequest) -> dict[str, Any]:
        task = app.state.recruiting.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["status"] not in {"pending_review", "approved", "failed"}:
            raise HTTPException(status_code=409, detail="任务已经处理")
        if not task.get("boss_key"):
            raise HTTPException(status_code=409, detail="候选人尚未绑定 BOSS 会话")
        text = (payload.text or task["draft"]).strip()
        if not text or len(text) > 2000:
            raise HTTPException(status_code=422, detail="消息长度必须为 1 到 2000 个字符")
        try:
            message = app.state.boss.send(task["boss_key"], text)
        except BossError:
            app.state.recruiting.update_task(task_id, "failed")
            raise
        app.state.recruiting.add_message(task["candidate_id"], "boss", "agent", text)
        return {
            "task": app.state.recruiting.update_task(task_id, "sent"),
            "message": message,
        }

    @app.post("/api/tasks/{task_id}/dismiss", dependencies=[Depends(require_session)])
    def dismiss_task(task_id: int) -> dict[str, Any]:
        try:
            return app.state.recruiting.update_task(task_id, "dismissed")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="任务不存在") from exc

    def change_greeting_plan(operation: Any) -> dict[str, Any]:
        try:
            return operation()
        except PlanConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="主动招呼计划不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/greeting-plans", dependencies=[Depends(require_session)])
    def greeting_plans() -> dict[str, Any]:
        return app.state.greetings.list_plans()

    @app.post("/api/greeting-plans", dependencies=[Depends(require_session)])
    def create_greeting_plan(payload: GreetingPlanRequest) -> dict[str, Any]:
        changes = payload.model_dump(exclude_none=True)
        return change_greeting_plan(
            lambda: app.state.greetings.create_plan(**changes)
        )

    @app.patch(
        "/api/greeting-plans/{plan_id}", dependencies=[Depends(require_session)]
    )
    def update_greeting_plan(
        plan_id: int, payload: GreetingPlanRequest
    ) -> dict[str, Any]:
        changes = payload.model_dump(exclude_none=True)
        return change_greeting_plan(
            lambda: app.state.greetings.update_plan(plan_id, **changes)
        )

    @app.delete(
        "/api/greeting-plans/{plan_id}", dependencies=[Depends(require_session)]
    )
    def delete_greeting_plan(plan_id: int) -> dict[str, bool]:
        try:
            app.state.greetings.delete_plan(plan_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="主动招呼计划不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"deleted": True}

    @app.get("/api/greetings/logs", dependencies=[Depends(require_session)])
    def greeting_logs(limit: int = 50) -> list[dict[str, Any]]:
        return app.state.greetings.logs(limit=limit)

    @app.post(
        "/api/greeting-plans/{plan_id}/run-once",
        dependencies=[Depends(require_session)],
    )
    def run_greeting_once(plan_id: int) -> dict[str, Any]:
        try:
            return app.state.greetings.run_once(plan_id, manual=True)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="主动招呼计划不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"}
        )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
