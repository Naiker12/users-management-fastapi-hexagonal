from __future__ import annotations

import logging
from collections.abc import Generator
from uuid import UUID

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from users_management.application import UserService
from users_management.config import get_settings
from users_management.domain import (
    DomainError,
    InvalidCredentials,
    UserAlreadyExists,
    UserNotFound,
)
from users_management.infrastructure import EmailSender, Security, UserRepository, make_engine

logging.basicConfig(level=logging.INFO)
settings = get_settings()
engine = make_engine(settings)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
security_service = Security(settings)
email_sender = EmailSender(settings)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    role: str = "MEMBER"


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = None
    status: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_service(session: Session = Depends(get_session)) -> UserService:
    return UserService(UserRepository(session), security_service, email_sender)


def user_response(user) -> dict:
    return {"id": str(user.id), "name": user.name, "email": user.email,
            "role": user.role.value, "status": user.status.value}


def create_app() -> FastAPI:
    app = FastAPI(title="Users Management API", version="1.0.0", docs_url=None,
                  redoc_url=None, openapi_url="/v3/api-docs")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(DomainError)
    async def domain_error_handler(_, exc: DomainError):
        if isinstance(exc, InvalidCredentials):
            status = 401
        elif isinstance(exc, UserNotFound):
            status = 404
        elif isinstance(exc, UserAlreadyExists):
            status = 409
        else:
            status = 400
        return __import__("fastapi").responses.JSONResponse(status_code=status,
            content={"status": status, "message": str(exc)})

    def current_user(authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, detail="Autenticacion requerida o token invalido.",
                                headers={"WWW-Authenticate": "Bearer"})
        try:
            return security_service.decode(authorization[7:])
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(401, detail="Autenticacion requerida o token invalido.",
                                headers={"WWW-Authenticate": "Bearer"}) from None

    @app.exception_handler(HTTPException)
    async def http_error_handler(_, exc: HTTPException):
        if exc.status_code == 401:
            return __import__("fastapi").responses.JSONResponse(status_code=401,
                content={"status": 401, "message": "Autenticacion requerida o token invalido."},
                headers=exc.headers)
        return __import__("fastapi").responses.JSONResponse(status_code=exc.status_code,
            content={"status": exc.status_code, "message": str(exc.detail)})

    @app.get("/swagger-ui/index.html", include_in_schema=False)
    async def swagger_ui():
        return get_swagger_ui_html(openapi_url="/v3/api-docs", title="Users Management API")

    @app.get("/", include_in_schema=False)
    def root(_: dict = Depends(current_user)):
        return {"message": "Users Management API"}

    @app.post("/api/auth/login")
    def login(body: LoginRequest, service: UserService = Depends(get_service)):
        token, expires = service.login(body.email, body.password)
        return {"accessToken": token, "tokenType": "Bearer", "expiresIn": expires}

    @app.post("/api/users", status_code=201)
    def create_user(body: UserCreate, service: UserService = Depends(get_service)):
        return user_response(service.create(body.model_dump()))

    @app.get("/api/users")
    def list_users(_: dict = Depends(current_user), service: UserService = Depends(get_service)):
        return [user_response(user) for user in service.list()]

    @app.get("/api/users/{user_id}")
    def get_user(user_id: UUID, _: dict = Depends(current_user), service: UserService = Depends(get_service)):
        return user_response(service.get(user_id))

    @app.put("/api/users/{user_id}")
    def update_user(user_id: UUID, body: UserUpdate, _: dict = Depends(current_user),
                    service: UserService = Depends(get_service)):
        return user_response(service.update(user_id, body.model_dump(exclude_unset=True, exclude_none=True)))

    @app.delete("/api/users/{user_id}", status_code=204)
    def delete_user(user_id: UUID, _: dict = Depends(current_user),
                    service: UserService = Depends(get_service)):
        service.delete(user_id)
        return Response(status_code=204)

    return app


app = create_app()
