# api/main.py
# Quote-to-Invoice Platform
# FastAPI application entry point.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.logger import configure_logging
from api.health_router import router as health_router
from api.quote_router import router as quote_router
from api.order_router import router as order_router
from api.auth_router import router as auth_router
from api.catalog_router import router as catalog_router
from api.pricing_router import router as pricing_router

# Configure structured logging on startup
configure_logging()

app = FastAPI(
    title="Quote-to-Invoice Platform",
    description=(
        "Pricing configurator, branded PDF quote generation, "
        "QuickBooks Online invoice push, and Monday.com production item creation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://quote.datawebify.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(quote_router)
app.include_router(order_router)
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(pricing_router)


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return {
        "app": "Quote-to-Invoice Platform",
        "docs": "/docs",
        "health": "/health",
    }
