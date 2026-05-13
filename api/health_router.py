# api/health_router.py
# AgAI_27 - Quote-to-Invoice Platform
# Health and connectivity check endpoints.

from fastapi import APIRouter
from datetime import datetime, timezone
from core.config import get_settings

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health")
def health_check():
    """Basic liveness check. Returns 200 if the app is running."""
    return {
        "status": "ok",
        "app": "AgAI_27 Quote-to-Invoice Platform",
        "env": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/qbo")
def qbo_health():
    """Check QuickBooks Online API connectivity."""
    from integrations.qbo_invoice_client import check_qbo_connection
    connected = check_qbo_connection()
    return {
        "service": "QuickBooks Online",
        "connected": connected,
        "realm_id": settings.quickbooks_realm_id or "not configured",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/monday")
def monday_health():
    """Check Monday.com API connectivity."""
    from integrations.monday_client import check_monday_connection
    connected = check_monday_connection()
    return {
        "service": "Monday.com",
        "connected": connected,
        "board_id": settings.monday_board_id or "not configured",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
