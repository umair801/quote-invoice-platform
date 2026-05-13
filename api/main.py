# api/main.py
# AgAI_27 - Quote-to-Invoice Platform
# FastAPI application entry point.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.logger import configure_logging
from api.health_router import router as health_router
from api.quote_router import router as quote_router
from api.order_router import router as order_router
from api.auth_router import router as auth_router

# Configure structured logging on startup
configure_logging()

app = FastAPI(
    title="AgAI_27 Quote-to-Invoice Platform",
    description=(
        "Pricing configurator, branded PDF quote generation, "
        "QuickBooks Online invoice push, and Monday.com production item creation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=True,
)

# CORS - restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(quote_router)
app.include_router(order_router)
app.include_router(auth_router)


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return {
        "app": "AgAI_27 Quote-to-Invoice Platform",
        "docs": "/docs",
        "health": "/health",
    }
