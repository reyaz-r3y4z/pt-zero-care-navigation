"""FastAPI application factory, authenticated routes, and static UI."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents import Coordinator
from app.auth import AuthService, SESSION_HOURS
from app.models import (
    AuthResponse, LoginRequest, NavigationResponse, PatientRequest, RegisterRequest, UserPublic,
)
from app.rag import KnowledgeBase
from app.repository import Repository
from app.synthetic import SyntheticPatientGenerator


BASE = Path(__file__).parent
SESSION_COOKIE = "pt_zero_session"
CSRF_COOKIE = "pt_zero_csrf"


def env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def set_auth_cookies(response: Response, token: str, csrf_token: str, secure: bool) -> None:
    max_age = SESSION_HOURS * 60 * 60
    response.set_cookie(
        SESSION_COOKIE, token, max_age=max_age, httponly=True,
        secure=secure, samesite="strict", path="/",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token, max_age=max_age, httponly=False,
        secure=secure, samesite="strict", path="/",
    )


def clear_auth_cookies(response: Response, secure: bool) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="strict")


def create_app(database_path: Path | None = None) -> FastAPI:
    resolved_database = database_path or Path(
        os.getenv("DATABASE_PATH", str(BASE / "data" / "pt_zero.db"))
    )
    cookie_secure = env_flag("COOKIE_SECURE")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = Repository(resolved_database)
        app.state.repository = repository
        app.state.auth = AuthService(repository)
        app.state.coordinator = Coordinator(
            repository, KnowledgeBase(BASE / "data" / "knowledge.json")
        )
        yield
        repository.close()

    app = FastAPI(
        title="PT Zero Care Navigation", version="2.0.0", lifespan=lifespan,
        description="Authenticated, synthetic-only multi-agent care-navigation learning MVP.",
    )
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def current_session(
        request: Request,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> dict:
        session = request.app.state.auth.authenticate(session_token)
        if not session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        session["raw_token"] = session_token
        return session

    def csrf_session(
        request: Request,
        session: dict = Depends(current_session),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
        csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    ) -> dict:
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
        if not request.app.state.auth.verify_csrf(session, csrf_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
        return session

    @app.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(BASE / "static" / "index.html")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "healthy", "synthetic_only": True, "agents": 7, "auth": "enabled"}

    @app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
    def register(payload: RegisterRequest, response: Response, request: Request) -> AuthResponse:
        try:
            issued = request.app.state.auth.register(
                payload.email, payload.display_name, payload.password
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        set_auth_cookies(response, issued.token, issued.csrf_token, cookie_secure)
        return AuthResponse(
            user=UserPublic.model_validate(request.app.state.auth.public_user(issued.user)),
            message="Account created",
        )

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest, response: Response, request: Request) -> AuthResponse:
        try:
            issued = request.app.state.auth.login(payload.email, payload.password)
        except ValueError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        set_auth_cookies(response, issued.token, issued.csrf_token, cookie_secure)
        return AuthResponse(
            user=UserPublic.model_validate(request.app.state.auth.public_user(issued.user)),
            message="Signed in",
        )

    @app.get("/api/auth/me", response_model=UserPublic)
    def me(request: Request, session: dict = Depends(current_session)) -> UserPublic:
        return UserPublic.model_validate(request.app.state.auth.public_user(session))

    @app.post("/api/auth/logout", status_code=204)
    def logout(
        request: Request, response: Response,
        session: dict = Depends(csrf_session),
    ) -> Response:
        request.app.state.auth.logout(session["raw_token"])
        clear_auth_cookies(response, cookie_secure)
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    @app.get("/api/sample-cases")
    def sample_cases(
        session: dict = Depends(current_session),
        count: int = Query(default=5, ge=1, le=50),
        seed: int = Query(default=42),
    ) -> list[dict]:
        return SyntheticPatientGenerator(seed).generate(count)

    @app.get("/api/providers")
    def providers(
        request: Request, session: dict = Depends(current_session)
    ) -> list[dict]:
        return request.app.state.repository.providers()

    @app.post("/api/navigate", response_model=NavigationResponse)
    def navigate(
        patient: PatientRequest, request: Request,
        session: dict = Depends(csrf_session),
    ) -> NavigationResponse:
        return request.app.state.coordinator.navigate(patient)

    return app


app = create_app()
