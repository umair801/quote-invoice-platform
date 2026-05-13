# api/order_router.py
# AgAI_27 - Quote-to-Invoice Platform
# Order lifecycle endpoints: create from quote, fetch, list, sync to Monday.com.

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.models import (
    AgOrder,
    ClientInfo,
    QuoteLineItem,
    ArtworkSpec,
    AgOrderStatus,
    MondaySyncStatus,
)
from core.database import (
    get_quote_by_number,
    insert_order,
    get_order_by_number,
    update_order,
    list_orders,
)
from agents.monday_agent import MondayAgent
from agents.audit_logger_agent import AuditLoggerAgent

router = APIRouter(prefix="/orders", tags=["Orders"])
audit = AuditLoggerAgent()
monday_agent = MondayAgent()


# ─── Request schemas ──────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    quote_number: str
    notes:        Optional[str] = None
    sync_to_monday: bool        = True


class UpdateOrderStatusRequest(BaseModel):
    status: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_order_number() -> str:
    """Generate a unique order number. Format: ORD-YYYY-XXXX."""
    year = datetime.now(timezone.utc).year
    uid  = str(uuid4())[:4].upper()
    return f"ORD-{year}-{uid}"


def _order_to_db_dict(o: AgOrder) -> dict:
    """Flatten an AgOrder model to a Supabase-compatible dict."""
    return {
        "id":                 str(o.id),
        "order_number":       o.order_number,
        "quote_id":           str(o.quote_id),
        "quote_number":       o.quote_number,
        "client_name":        o.client.client_name,
        "client_id":          o.client.client_id,
        "contact_name":       o.client.contact_name,
        "contact_email":      o.client.contact_email,
        "contact_phone":      o.client.contact_phone,
        "billing_address":    o.client.billing_address,
        "qbo_customer_id":    o.client.qbo_customer_id,
        "artwork_width":      float(o.artwork.width_inches)  if o.artwork and o.artwork.width_inches  else None,
        "artwork_height":     float(o.artwork.height_inches) if o.artwork and o.artwork.height_inches else None,
        "artwork_medium":     o.artwork.medium               if o.artwork else None,
        "artwork_substrate":  o.artwork.substrate            if o.artwork else None,
        "artwork_notes":      o.artwork.notes                if o.artwork else None,
        "line_items":         [item.model_dump(mode="json") for item in o.line_items],
        "currency":           o.currency,
        "total":              float(o.total),
        "notes":              o.notes,
        "status":             o.status.value,
        "monday_sync_status": o.monday_sync_status.value,
        "created_at":         o.created_at.isoformat(),
        "updated_at":         o.updated_at.isoformat(),
    }


def _row_to_order_model(row: dict) -> AgOrder:
    """Reconstruct an AgOrder model from a Supabase DB row."""
    D = Decimal

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

    return AgOrder(
        id=row["id"],
        quote_id=row["quote_id"],
        order_number=row["order_number"],
        quote_number=row["quote_number"],
        client=client,
        artwork=artwork,
        line_items=line_items,
        currency=row.get("currency", "USD"),
        total=D(str(row.get("total", 0))),
        notes=row.get("notes"),
        status=AgOrderStatus(row.get("status", "draft")),
        monday_sync_status=MondaySyncStatus(row.get("monday_sync_status", "pending")),
        monday_item_id=row.get("monday_item_id"),
        monday_board_id=row.get("monday_board_id"),
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_order(body: CreateOrderRequest):
    """
    Create a production order from an approved quote.
    Optionally syncs immediately to Monday.com as a production item.
    """
    quote_row = get_quote_by_number(body.quote_number)
    if not quote_row:
        raise HTTPException(
            status_code=404,
            detail=f"Quote {body.quote_number} not found.",
        )

    if quote_row.get("status") != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Only approved quotes can generate orders. Quote status: {quote_row.get('status')}",
        )

    D = Decimal
    client = ClientInfo(
        client_name=quote_row.get("client_name", ""),
        client_id=quote_row.get("client_id"),
        contact_name=quote_row.get("contact_name"),
        contact_email=quote_row.get("contact_email"),
        contact_phone=quote_row.get("contact_phone"),
        billing_address=quote_row.get("billing_address"),
        qbo_customer_id=quote_row.get("qbo_customer_id"),
    )

    artwork = None
    if quote_row.get("artwork_width") or quote_row.get("artwork_height"):
        artwork = ArtworkSpec(
            width_inches=D(str(quote_row["artwork_width"]))   if quote_row.get("artwork_width")  else None,
            height_inches=D(str(quote_row["artwork_height"])) if quote_row.get("artwork_height") else None,
            medium=quote_row.get("artwork_medium"),
            substrate=quote_row.get("artwork_substrate"),
            notes=quote_row.get("artwork_notes"),
        )

    raw_items = quote_row.get("line_items") or []
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

    order = AgOrder(
        order_number=_generate_order_number(),
        quote_id=quote_row["id"],
        quote_number=body.quote_number,
        client=client,
        artwork=artwork,
        line_items=line_items,
        currency=quote_row.get("currency", "USD"),
        total=D(str(quote_row.get("total", 0))),
        notes=body.notes or quote_row.get("notes"),
        status=AgOrderStatus.CONFIRMED,
        monday_sync_status=MondaySyncStatus.PENDING,
    )

    try:
        db_row = insert_order(_order_to_db_dict(order))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {exc}")

    audit.log_order_created(order.order_number, body.quote_number)

    monday_result = None
    if body.sync_to_monday:
        monday_result = monday_agent.sync(order)

    return {
        "order_number":    order.order_number,
        "quote_number":    body.quote_number,
        "status":          order.status.value,
        "total":           float(order.total),
        "currency":        order.currency,
        "db_id":           db_row.get("id"),
        "monday_synced":   monday_result.success if monday_result else False,
        "monday_item_id":  monday_result.monday_item_id if monday_result else None,
        "monday_error":    monday_result.error_message if monday_result and not monday_result.success else None,
    }


@router.get("/")
def list_all_orders(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit:  int           = Query(default=50, le=200),
):
    """List orders, optionally filtered by status."""
    rows = list_orders(status=status, limit=limit)
    return {"count": len(rows), "orders": rows}


@router.get("/{order_number}")
def get_order(order_number: str):
    """Fetch a single order by order_number."""
    row = get_order_by_number(order_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found.")
    return row


@router.post("/{order_number}/sync-monday")
def sync_order_to_monday(order_number: str):
    """
    Manually trigger a Monday.com sync for a confirmed order.
    Useful for retrying failed syncs.
    """
    row = get_order_by_number(order_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found.")

    if row.get("status") not in ("confirmed", "draft"):
        raise HTTPException(
            status_code=400,
            detail=f"Order status is {row.get('status')}. Only confirmed or draft orders can be synced.",
        )

    order = _row_to_order_model(row)
    result = monday_agent.sync(order)

    return {
        "order_number":   order_number,
        "success":        result.success,
        "monday_item_id": result.monday_item_id,
        "monday_board_id": result.monday_board_id,
        "error":          result.error_message,
    }


@router.patch("/{order_number}/status")
def update_order_status(order_number: str, body: UpdateOrderStatusRequest):
    """
    Update the production status of an order.
    Valid values: draft, confirmed, in_production, completed, cancelled.
    """
    valid_statuses = [s.value for s in AgOrderStatus]
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {valid_statuses}",
        )

    row = get_order_by_number(order_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found.")

    now = datetime.now(timezone.utc).isoformat()
    update_order(order_number, {
        "status":     body.status,
        "updated_at": now,
    })

    return {
        "order_number": order_number,
        "status":        body.status,
        "updated_at":    now,
    }
