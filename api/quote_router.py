# api/quote_router.py
# AgAI_27 - Quote-to-Invoice Platform
# Quote lifecycle endpoints: create, fetch, list, approve, reject, sync to QBO.

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.models import (
    Quote,
    ClientInfo,
    QuoteLineItem,
    ArtworkSpec,
    QuoteStatus,
    QBOSyncStatus,
)
from core.database import (
    insert_quote,
    get_quote_by_number,
    update_quote,
    list_quotes,
)
from agents.qbo_sync_agent import QBOSyncAgent
from agents.audit_logger_agent import AuditLoggerAgent

router = APIRouter(prefix="/quotes", tags=["Quotes"])
audit = AuditLoggerAgent()
qbo_agent = QBOSyncAgent()


# ─── Request / Response schemas ───────────────────────────────────────────────

class QuoteLineItemRequest(BaseModel):
    line_number:  int
    category:     str
    description:  str
    quantity:     Decimal
    unit_price:   Decimal
    sku:          Optional[str] = None
    notes:        Optional[str] = None


class ArtworkSpecRequest(BaseModel):
    width_inches:  Optional[Decimal] = None
    height_inches: Optional[Decimal] = None
    medium:        Optional[str]     = None
    substrate:     Optional[str]     = None
    notes:         Optional[str]     = None


class ClientInfoRequest(BaseModel):
    client_name:     str
    client_id:       Optional[str] = None
    contact_name:    Optional[str] = None
    contact_email:   Optional[str] = None
    contact_phone:   Optional[str] = None
    billing_address: Optional[str] = None
    qbo_customer_id: Optional[str] = None


class CreateQuoteRequest(BaseModel):
    client:     ClientInfoRequest
    line_items: list[QuoteLineItemRequest]
    artwork:    Optional[ArtworkSpecRequest] = None
    currency:   str                          = "USD"
    tax:        Decimal                      = Decimal("0")
    notes:      Optional[str]                = None
    valid_days: int                          = 30


class ApproveQuoteRequest(BaseModel):
    sync_to_qbo: bool = True


class RejectQuoteRequest(BaseModel):
    reason: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_quote_number() -> str:
    """Generate a sequential quote number. Format: QT-YYYY-XXXX."""
    year = datetime.now(timezone.utc).year
    uid  = str(uuid4())[:4].upper()
    return f"QT-{year}-{uid}"


def _compute_totals(
    line_items: list[QuoteLineItemRequest],
    tax: Decimal,
) -> tuple[list[QuoteLineItem], Decimal, Decimal]:
    """Compute line totals, subtotal, and grand total."""
    built_items = []
    subtotal = Decimal("0")

    for item in line_items:
        total = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        subtotal += total
        built_items.append(QuoteLineItem(
            line_number=item.line_number,
            category=item.category,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total=total,
            sku=item.sku,
            notes=item.notes,
        ))

    grand_total = (subtotal + tax).quantize(Decimal("0.01"))
    return built_items, subtotal, grand_total


def _quote_to_db_dict(q: Quote) -> dict:
    """Flatten a Quote model to a Supabase-compatible dict."""
    return {
        "id":                str(q.id),
        "quote_number":      q.quote_number,
        "client_name":       q.client.client_name,
        "client_id":         q.client.client_id,
        "contact_name":      q.client.contact_name,
        "contact_email":     q.client.contact_email,
        "contact_phone":     q.client.contact_phone,
        "billing_address":   q.client.billing_address,
        "qbo_customer_id":   q.client.qbo_customer_id,
        "artwork_width":     float(q.artwork.width_inches)  if q.artwork and q.artwork.width_inches  else None,
        "artwork_height":    float(q.artwork.height_inches) if q.artwork and q.artwork.height_inches else None,
        "artwork_medium":    q.artwork.medium               if q.artwork else None,
        "artwork_substrate": q.artwork.substrate            if q.artwork else None,
        "artwork_notes":     q.artwork.notes                if q.artwork else None,
        "line_items":        [item.model_dump(mode="json") for item in q.line_items],
        "currency":          q.currency,
        "subtotal":          float(q.subtotal),
        "tax":               float(q.tax),
        "total":             float(q.total),
        "notes":             q.notes,
        "valid_days":        q.valid_days,
        "status":            q.status.value,
        "qbo_sync_status":   q.qbo_sync_status.value,
        "created_at":        q.created_at.isoformat(),
        "updated_at":        q.updated_at.isoformat(),
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_quote(body: CreateQuoteRequest):
    """
    Create a new quote from pricing configurator output.
    Computes line totals and grand total automatically.
    """
    line_items, subtotal, total = _compute_totals(body.line_items, body.tax)

    quote = Quote(
        quote_number=_generate_quote_number(),
        client=ClientInfo(**body.client.model_dump()),
        artwork=ArtworkSpec(**body.artwork.model_dump()) if body.artwork else None,
        line_items=line_items,
        currency=body.currency,
        subtotal=subtotal,
        tax=body.tax,
        total=total,
        notes=body.notes,
        valid_days=body.valid_days,
        status=QuoteStatus.DRAFT,
        qbo_sync_status=QBOSyncStatus.PENDING,
    )

    try:
        db_row = insert_quote(_quote_to_db_dict(quote))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {exc}")

    audit.log_quote_created(quote.quote_number)

    return {
        "quote_number": quote.quote_number,
        "status":        quote.status.value,
        "total":         float(quote.total),
        "currency":      quote.currency,
        "db_id":         db_row.get("id"),
    }


@router.get("/")
def list_all_quotes(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit:  int           = Query(default=50, le=200),
):
    """List quotes, optionally filtered by status."""
    rows = list_quotes(status=status, limit=limit)
    return {"count": len(rows), "quotes": rows}


@router.get("/{quote_number}")
def get_quote(quote_number: str):
    """Fetch a single quote by quote_number."""
    row = get_quote_by_number(quote_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found.")
    return row


@router.post("/{quote_number}/approve")
def approve_quote(quote_number: str, body: ApproveQuoteRequest):
    """
    Mark a quote as approved.
    If sync_to_qbo is True, immediately pushes a customer Invoice to QuickBooks.
    """
    row = get_quote_by_number(quote_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found.")

    if row.get("status") not in ("draft", "sent"):
        raise HTTPException(
            status_code=400,
            detail=f"Quote is already {row.get('status')}. Only draft or sent quotes can be approved.",
        )

    now = datetime.now(timezone.utc).isoformat()
    update_quote(quote_number, {
        "status":      QuoteStatus.APPROVED.value,
        "approved_at": now,
        "updated_at":  now,
    })

    audit.log_quote_approved(quote_number)

    qbo_result = None
    if body.sync_to_qbo:
        # Rebuild Quote model from DB row for QBO sync
        quote = _row_to_quote_model(row)
        quote.status = QuoteStatus.APPROVED
        qbo_result = qbo_agent.sync(quote)

    return {
        "quote_number": quote_number,
        "status":        "approved",
        "qbo_synced":    qbo_result.success if qbo_result else False,
        "qbo_invoice_id": qbo_result.qbo_invoice_id if qbo_result else None,
        "qbo_error":     qbo_result.error_message if qbo_result and not qbo_result.success else None,
    }


@router.post("/{quote_number}/reject")
def reject_quote(quote_number: str, body: RejectQuoteRequest):
    """Mark a quote as rejected with a reason."""
    row = get_quote_by_number(quote_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found.")

    if row.get("status") not in ("draft", "sent"):
        raise HTTPException(
            status_code=400,
            detail=f"Quote is already {row.get('status')}. Only draft or sent quotes can be rejected.",
        )

    now = datetime.now(timezone.utc).isoformat()
    update_quote(quote_number, {
        "status":           QuoteStatus.REJECTED.value,
        "rejected_at":      now,
        "rejection_reason": body.reason,
        "updated_at":       now,
    })

    audit.log_quote_rejected(quote_number, body.reason)

    return {
        "quote_number": quote_number,
        "status":        "rejected",
        "reason":        body.reason,
    }


@router.post("/{quote_number}/send")
def mark_quote_sent(quote_number: str, recipient_email: str = Query(...)):
    """Mark a quote as sent to the client."""
    row = get_quote_by_number(quote_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found.")

    if row.get("status") != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Only draft quotes can be marked as sent. Current status: {row.get('status')}",
        )

    now = datetime.now(timezone.utc).isoformat()
    update_quote(quote_number, {
        "status":     QuoteStatus.SENT.value,
        "sent_at":    now,
        "updated_at": now,
    })

    audit.log_quote_sent(quote_number, recipient_email)

    return {
        "quote_number":    quote_number,
        "status":          "sent",
        "recipient_email": recipient_email,
    }


@router.post("/{quote_number}/sync-qbo")
def sync_quote_to_qbo(quote_number: str):
    """
    Manually trigger a QBO invoice sync for an approved quote.
    Useful for retrying failed syncs.
    """
    row = get_quote_by_number(quote_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found.")

    if row.get("status") != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Only approved quotes can be synced to QBO. Current status: {row.get('status')}",
        )

    quote = _row_to_quote_model(row)
    result = qbo_agent.sync(quote)

    return {
        "quote_number":    quote_number,
        "success":         result.success,
        "qbo_invoice_id":  result.qbo_invoice_id,
        "qbo_invoice_number": result.qbo_invoice_number,
        "error":           result.error_message,
    }


# ─── Internal model builder ───────────────────────────────────────────────────

def _row_to_quote_model(row: dict) -> Quote:
    """Reconstruct a Quote model from a Supabase DB row."""
    from decimal import Decimal as D

    client = ClientInfo(
        client_name=row.get("client_name", ""),
        client_id=row.get("client_id"),
        contact_name=row.get("contact_name"),
        contact_email=row.get("contact_email"),
        contact_phone=row.get("contact_phone"),
        billing_address=row.get("billing_address"),
        qbo_customer_id=row.get("qbo_customer_id"),
    )

    artwork = None
    if row.get("artwork_width") or row.get("artwork_height"):
        artwork = ArtworkSpec(
            width_inches=D(str(row["artwork_width"]))   if row.get("artwork_width")  else None,
            height_inches=D(str(row["artwork_height"])) if row.get("artwork_height") else None,
            medium=row.get("artwork_medium"),
            substrate=row.get("artwork_substrate"),
            notes=row.get("artwork_notes"),
        )

    raw_items = row.get("line_items") or []
    line_items = [
        QuoteLineItem(
            line_number=i.get("line_number", idx + 1),
            category=i.get("category", ""),
            description=i.get("description", ""),
            quantity=D(str(i.get("quantity", 1))),
            unit_price=D(str(i.get("unit_price", 0))),
            total=D(str(i.get("total", 0))),
            sku=i.get("sku"),
            notes=i.get("notes"),
        )
        for idx, i in enumerate(raw_items)
    ]

    return Quote(
        quote_number=row["quote_number"],
        client=client,
        artwork=artwork,
        line_items=line_items,
        currency=row.get("currency", "USD"),
        subtotal=D(str(row.get("subtotal", 0))),
        tax=D(str(row.get("tax", 0))),
        total=D(str(row.get("total", 0))),
        notes=row.get("notes"),
        valid_days=row.get("valid_days", 30),
        status=QuoteStatus(row.get("status", "draft")),
        qbo_sync_status=QBOSyncStatus(row.get("qbo_sync_status", "pending")),
    )
