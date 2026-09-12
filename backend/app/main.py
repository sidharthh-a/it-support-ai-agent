from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.tickets import router as tickets_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.devices import router as devices_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.admin import router as admin_router

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware — explicit allow-list only (no wildcard).
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

# Production hardening middleware (order matters: outermost first)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions with the request id and return a safe 500."""
    request_id = getattr(request.state, "request_id", "-")
    from app.core.logging import logger
    logger.exception("Unhandled exception [request_id=%s] %s %s: %s",
                     request_id, request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


# Include API v1 routers
app.include_router(health_router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["AI Chat Agent"])
app.include_router(conversations_router, prefix=f"{settings.API_V1_STR}/conversations", tags=["Conversations"])
app.include_router(tickets_router, prefix=f"{settings.API_V1_STR}/tickets", tags=["Support Tickets"])
app.include_router(incidents_router, prefix=f"{settings.API_V1_STR}/incidents", tags=["Incidents"])
app.include_router(knowledge_router, prefix=f"{settings.API_V1_STR}/knowledge", tags=["Knowledge Base"])
app.include_router(devices_router, prefix=f"{settings.API_V1_STR}/devices", tags=["Devices"])
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics"])
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin"])


@app.get("/")
def root():
    return {
        "message": "Welcome to IT Support AI Agent API",
        "docs": "/docs",
        "version": settings.VERSION
    }
