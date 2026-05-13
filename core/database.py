# core/database.py

import structlog
from supabase import create_client, Client
from core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_client: Client | None = None


def get_supabase() -> Client:
    """Return a singleton Supabase client."""
    global _client
    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY,
        )
        logger.info("supabase_client_initialized", url=settings.SUPABASE_URL)
    return _client


def insert_invoice(data: dict) -> dict:
    client = get_supabase()
    result = client.table("ap_invoices").insert(data).execute()
    return result.data[0] if result.data else {}


def update_invoice_status(invoice_number: str, status: str, **kwargs) -> dict:
    client = get_supabase()
    payload = {"status": status, **kwargs}
    result = (
        client.table("ap_invoices")
        .update(payload)
        .eq("invoice_number", invoice_number)
        .execute()
    )
    return result.data[0] if result.data else {}


def get_existing_invoice_numbers() -> list[str]:
    """Return all invoice numbers already stored in Supabase for duplicate detection."""
    client = get_supabase()
    result = client.table("ap_invoices").select("invoice_number").execute()
    return [
        row["invoice_number"]
        for row in (result.data or [])
        if row.get("invoice_number")
    ]


def insert_audit_entry(data: dict) -> dict:
    client = get_supabase()
    result = client.table("ap_audit_log").insert(data).execute()
    return result.data[0] if result.data else {}


def insert_exception(data: dict) -> dict:
    client = get_supabase()
    result = client.table("ap_exceptions").insert(data).execute()
    return result.data[0] if result.data else {}


def insert_approval(data: dict) -> dict:
    client = get_supabase()
    result = client.table("ap_approval_records").insert(data).execute()
    return result.data[0] if result.data else {}


def update_approval(approval_id: str, data: dict) -> dict:
    client = get_supabase()
    result = (
        client.table("ap_approval_records")
        .update(data)
        .eq("approval_id", approval_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def insert_payment(data: dict) -> dict:
    client = get_supabase()
    result = client.table("ap_payments").insert(data).execute()
    return result.data[0] if result.data else {}


def get_metrics() -> dict:
    client = get_supabase()

    total = client.table("ap_invoices").select("id", count="exact").execute()
    matched = (
        client.table("ap_invoices")
        .select("id", count="exact")
        .eq("status", "matched")
        .execute()
    )
    exceptions = (
        client.table("ap_exceptions")
        .select("id", count="exact")
        .eq("resolved", False)
        .execute()
    )
    paid = (
        client.table("ap_invoices")
        .select("id", count="exact")
        .eq("status", "paid")
        .execute()
    )

    return {
        "invoices_processed": total.count or 0,
        "invoices_matched": matched.count or 0,
        "invoices_paid": paid.count or 0,
        "open_exceptions": exceptions.count or 0,
    }


# =============================================================================
# Quote-to-Invoice Platform DB Functions
# =============================================================================

# --- Quotes ------------------------------------------------------------------

def insert_quote(data: dict) -> dict:
    """Insert a new quote record into the quote_quotes table."""
    client = get_supabase()
    result = client.table("quote_quotes").insert(data).execute()
    return result.data[0] if result.data else {}


def get_quote_by_number(quote_number: str) -> dict:
    """Fetch a single quote by quote_number."""
    client = get_supabase()
    result = (
        client.table("quote_quotes")
        .select("*")
        .eq("quote_number", quote_number)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


def get_quote_by_id(quote_id: str) -> dict:
    """Fetch a single quote by UUID."""
    client = get_supabase()
    result = (
        client.table("quote_quotes")
        .select("*")
        .eq("id", quote_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


def update_quote(quote_number: str, payload: dict) -> dict:
    """Update fields on a quote by quote_number."""
    client = get_supabase()
    result = (
        client.table("quote_quotes")
        .update(payload)
        .eq("quote_number", quote_number)
        .execute()
    )
    return result.data[0] if result.data else {}


def list_quotes(status: str = None, limit: int = 50) -> list:
    """List quotes, optionally filtered by status."""
    client = get_supabase()
    query = client.table("quote_quotes").select("*").order("created_at", desc=True).limit(limit)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data or []


# --- Orders ------------------------------------------------------------------

def insert_order(data: dict) -> dict:
    """Insert a new order record into the quote_orders table."""
    client = get_supabase()
    result = client.table("quote_orders").insert(data).execute()
    return result.data[0] if result.data else {}


def get_order_by_number(order_number: str) -> dict:
    """Fetch a single order by order_number."""
    client = get_supabase()
    result = (
        client.table("quote_orders")
        .select("*")
        .eq("order_number", order_number)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


def update_order(order_number: str, payload: dict) -> dict:
    """Update fields on an order by order_number."""
    client = get_supabase()
    result = (
        client.table("quote_orders")
        .update(payload)
        .eq("order_number", order_number)
        .execute()
    )
    return result.data[0] if result.data else {}


def list_orders(status: str = None, limit: int = 50) -> list:
    """List orders, optionally filtered by status."""
    client = get_supabase()
    query = client.table("quote_orders").select("*").order("created_at", desc=True).limit(limit)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data or []


# --- Quote Audit Log ---------------------------------------------------------

def insert_quote_audit(data: dict) -> dict:
    """Insert an audit entry for a quote or order state transition."""
    client = get_supabase()
    result = client.table("quote_audit_log").insert(data).execute()
    return result.data[0] if result.data else {}


# --- Catalog -----------------------------------------------------------------

def insert_catalog_item(data: dict) -> dict:
    """Insert a new catalog item into quote_catalog."""
    client = get_supabase()
    result = client.table("quote_catalog").insert(data).execute()
    return result.data[0] if result.data else {}


def get_catalog_item_by_sku(sku: str) -> dict:
    """Fetch a single catalog item by SKU. Returns {} if not found."""
    client = get_supabase()
    result = (
        client.table("quote_catalog")
        .select("*")
        .eq("sku", sku)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


def get_catalog_item_by_id(item_id: str) -> dict:
    """Fetch a single catalog item by UUID. Returns {} if not found."""
    client = get_supabase()
    result = (
        client.table("quote_catalog")
        .select("*")
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


def update_catalog_item(item_id: str, payload: dict) -> dict:
    """Update fields on a catalog item by UUID."""
    client = get_supabase()
    result = (
        client.table("quote_catalog")
        .update(payload)
        .eq("id", item_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def delete_catalog_item(item_id: str) -> bool:
    """Soft-delete a catalog item by setting is_active=False."""
    client = get_supabase()
    result = (
        client.table("quote_catalog")
        .update({"is_active": False})
        .eq("id", item_id)
        .execute()
    )
    return bool(result.data)


def list_catalog_items(
    category: str = None,
    active_only: bool = True,
    limit: int = 200,
) -> list:
    """List catalog items, optionally filtered by category and active status."""
    client = get_supabase()
    query = (
        client.table("quote_catalog")
        .select("*")
        .order("sort_order", desc=False)
        .order("name", desc=False)
        .limit(limit)
    )
    if category:
        query = query.eq("category", category)
    if active_only:
        query = query.eq("is_active", True)
    result = query.execute()
    return result.data or []
