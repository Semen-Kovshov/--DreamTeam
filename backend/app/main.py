"""Точка входа сервиса.

    uvicorn app.main:app --port 8030 --app-dir backend

Документация API — на /docs. Собранный фронтенд (frontend/dist) раздаётся
с того же порта: на защите поднимается один процесс.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import admin, routes
from .config import FRONTEND_DIST
from .scenarios.loader import load_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    routes.bind(load_all())
    yield


app = FastAPI(
    title="Вторая сторона — тренажёр переговоров",
    description="Кейс ЛЦТ 2026: свободный диалог с виртуальным оппонентом, "
                "детерминированное переговорное ядро, LLM как языковой слой, "
                "объяснимый разбор каждой партии.",
    version="0.1.0",
    lifespan=lifespan,
)

# Дев-фронтенд живёт на 5176; собранный — раздаётся отсюда же.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5176", "http://127.0.0.1:5176"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(admin.router)

if (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="ui")
else:
    @app.get("/")
    def root() -> dict:
        return {"service": "negotiation-sim", "docs": "/docs",
                "api": "/api/health",
                "note": "фронтенд не собран: npm run build --prefix frontend"}
