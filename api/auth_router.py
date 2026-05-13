# api/auth_router.py
# AgAI_27 - Quote-to-Invoice Platform
# QuickBooks Online OAuth2 flow: initiate, callback, status.

from __future__ import annotations

from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from core.config import get_settings
from core.logger import get_logger
from integrations.qbo_invoice_client import (
    build_authorization_url,
    exchange_code_for_tokens,
    check_qbo_connection,
    QBOAuthError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = get_logger(__name__)
settings = get_settings()

# JWT secret for signing the OAuth2 state parameter (CSRF protection)
# In production, use a dedicated SECRET_KEY env var
_STATE_SECRET = settings.quickbooks_client_secret or "dev-state-secret"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_state() -> str:
    """
    Generate a signed JWT as the OAuth2 state parameter.
    Prevents CSRF attacks during the OAuth2 callback.
    """
    payload = {
        "iat": datetime.now(timezone.utc).timestamp(),
        "purpose": "qbo_oauth",
    }
    return jwt.encode(payload, _STATE_SECRET, algorithm="HS256")


def _verify_state(state: str) -> bool:
    """Verify the OAuth2 state JWT. Returns True if valid."""
    try:
        jwt.decode(state, _STATE_SECRET, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/quickbooks")
def initiate_qbo_auth():
    """
    Step 1: Redirect the user to QuickBooks Online to authorize the app.
    Opens the QBO OAuth2 consent screen.
    """
    if not settings.quickbooks_client_id:
        raise HTTPException(
            status_code=500,
            detail="QUICKBOOKS_CLIENT_ID is not configured.",
        )

    state = _generate_state()
    auth_url = build_authorization_url(state=state)

    logger.info("qbo_oauth_initiated", redirect_uri=settings.quickbooks_redirect_uri)
    return RedirectResponse(url=auth_url)


@router.get("/quickbooks/callback")
def qbo_oauth_callback(
    code:     str = Query(..., description="Authorization code from QBO"),
    state:    str = Query(..., description="State parameter for CSRF verification"),
    realmId:  str = Query(..., description="QBO company realm ID"),
):
    """
    Step 2: QBO redirects here after the user authorizes the app.
    Exchanges the authorization code for access + refresh tokens.
    Store the returned tokens in your .env or secrets manager.
    """
    # Verify state to prevent CSRF
    if not _verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth2 state. Possible CSRF attempt.")

    try:
        tokens = exchange_code_for_tokens(code=code)
    except QBOAuthError as exc:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {exc}")

    access_token  = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in    = tokens.get("expires_in")

    logger.info(
        "qbo_oauth_complete",
        realm_id=realmId,
        expires_in=expires_in,
    )

    # In production: persist refresh_token and realmId to Supabase or secrets manager.
    # For now we return them so the developer can add them to .env manually.
    return {
        "message":       "QuickBooks authorization successful.",
        "realm_id":      realmId,
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "expires_in":    expires_in,
        "next_step": (
            "Copy QUICKBOOKS_REALM_ID and QUICKBOOKS_REFRESH_TOKEN "
            "into your .env file, then restart the server."
        ),
    }


@router.get("/quickbooks/status")
def qbo_connection_status():
    """
    Check whether the current QBO credentials are valid and connected.
    """
    if not settings.quickbooks_realm_id:
        return {
            "connected": False,
            "reason":    "QUICKBOOKS_REALM_ID not configured. Run /auth/quickbooks first.",
        }

    if not settings.quickbooks_refresh_token:
        return {
            "connected": False,
            "reason":    "QUICKBOOKS_REFRESH_TOKEN not configured. Run /auth/quickbooks first.",
        }

    connected = check_qbo_connection()
    return {
        "connected":  connected,
        "realm_id":   settings.quickbooks_realm_id,
        "env":        settings.app_env,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }
