# integrations/monday_client.py
# AgAI_27 - Quote-to-Invoice Platform
# Creates and updates production items on a Monday.com board when orders are approved.

from __future__ import annotations

from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

MONDAY_API_URL = "https://api.monday.com/v2"


class MondayAPIError(Exception):
    pass


# ─── Internal helpers ────────────────────────────────────────────────────────

def _get_headers() -> dict:
    """Build standard Monday.com API request headers."""
    return {
        "Authorization": settings.monday_api_key,
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }


def _run_query(query: str, variables: Optional[dict] = None) -> dict:
    """
    Execute a Monday.com GraphQL query or mutation.
    Returns the full response JSON.
    Raises MondayAPIError on HTTP or GraphQL errors.
    """
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    response = httpx.post(
        MONDAY_API_URL,
        headers=_get_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    # Monday returns errors inside the JSON body, not as HTTP status codes
    if "errors" in data:
        error_messages = [e.get("message", "unknown") for e in data["errors"]]
        raise MondayAPIError(f"Monday GraphQL error: {'; '.join(error_messages)}")

    return data


# ─── Board inspection ────────────────────────────────────────────────────────

def get_board_columns(board_id: str) -> list[dict]:
    """
    Return all columns on a Monday.com board.
    Used to inspect column IDs before building column_values payloads.
    """
    query = """
    query ($board_id: ID!) {
        boards(ids: [$board_id]) {
            columns {
                id
                title
                type
            }
        }
    }
    """
    data = _run_query(query, variables={"board_id": board_id})
    boards = data.get("data", {}).get("boards", [])
    if not boards:
        raise MondayAPIError(f"Board {board_id} not found or not accessible.")
    columns = boards[0].get("columns", [])
    logger.info("board_columns_fetched", board_id=board_id, count=len(columns))
    return columns


# ─── Item creation ───────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def create_production_item(
    board_id: str,
    item_name: str,
    order_number: str,
    quote_number: str,
    client_name: str,
    total: float,
    currency: str = "USD",
    notes: Optional[str] = None,
    group_id: Optional[str] = None,
) -> dict:
    """
    Create a production item on a Monday.com board for an approved order.
    Returns a dict with monday_item_id and monday_board_id.

    Column values use text columns only for maximum board compatibility.
    For custom column mappings, extend column_values below.
    """
    if not settings.monday_api_key:
        raise MondayAPIError("MONDAY_API_KEY is not configured.")

    if not board_id:
        raise MondayAPIError("monday_board_id is not configured.")

    # Build column values as JSON string
    # These map to standard text/number columns by their Monday column IDs.
    # Actual column IDs depend on the client's board setup.
    # We use a safe subset that works on any board with these column types.
    column_values = {
        "text":   order_number,       # Order Number column (type: text)
        "text1":  quote_number,       # Quote Number column (type: text)
        "text2":  client_name,        # Client Name column (type: text)
        "numbers": str(total),        # Total column (type: numbers)
        "text3":  currency,           # Currency column (type: text)
    }

    if notes:
        column_values["long_text"] = {"text": notes}

    import json
    column_values_str = json.dumps(column_values)

    if group_id:
        mutation = """
        mutation ($board_id: ID!, $group_id: String!, $item_name: String!, $column_values: JSON!) {
            create_item (
                board_id: $board_id,
                group_id: $group_id,
                item_name: $item_name,
                column_values: $column_values
            ) {
                id
                name
                board { id }
            }
        }
        """
        variables = {
            "board_id": board_id,
            "group_id": group_id,
            "item_name": item_name,
            "column_values": column_values_str,
        }
    else:
        mutation = """
        mutation ($board_id: ID!, $item_name: String!, $column_values: JSON!) {
            create_item (
                board_id: $board_id,
                item_name: $item_name,
                column_values: $column_values
            ) {
                id
                name
                board { id }
            }
        }
        """
        variables = {
            "board_id": board_id,
            "item_name": item_name,
            "column_values": column_values_str,
        }

    try:
        data = _run_query(mutation, variables=variables)
        item = data.get("data", {}).get("create_item", {})
        item_id = item.get("id")
        returned_board_id = item.get("board", {}).get("id", board_id)

        if not item_id:
            raise MondayAPIError("Monday returned no item ID after creation.")

        logger.info(
            "monday_item_created",
            item_id=item_id,
            board_id=returned_board_id,
            order_number=order_number,
        )

        return {
            "monday_item_id": item_id,
            "monday_board_id": returned_board_id,
            "item_name": item.get("name"),
        }

    except httpx.HTTPStatusError as exc:
        logger.error(
            "monday_http_error",
            order_number=order_number,
            status=exc.response.status_code,
            error=exc.response.text[:500],
        )
        raise MondayAPIError(f"Monday HTTP error: {exc}")


# ─── Item update ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def update_item_status(
    item_id: str,
    status_column_id: str,
    status_label: str,
) -> bool:
    """
    Update a status column on an existing Monday.com item.
    Returns True on success.
    """
    import json
    column_values_str = json.dumps({status_column_id: {"label": status_label}})

    mutation = """
    mutation ($item_id: ID!, $column_values: JSON!) {
        change_multiple_column_values (
            item_id: $item_id,
            board_id: 0,
            column_values: $column_values
        ) {
            id
        }
    }
    """
    try:
        _run_query(mutation, variables={
            "item_id": item_id,
            "column_values": column_values_str,
        })
        logger.info("monday_item_status_updated", item_id=item_id, status=status_label)
        return True
    except Exception as exc:
        logger.error("monday_item_status_failed", item_id=item_id, error=str(exc))
        return False


# ─── Health check ────────────────────────────────────────────────────────────

def check_monday_connection() -> bool:
    """
    Verify Monday.com API connectivity by fetching the current user.
    Returns True if connected, False otherwise.
    """
    query = "{ me { id name } }"
    try:
        data = _run_query(query)
        me = data.get("data", {}).get("me", {})
        logger.info("monday_connection_verified", user=me.get("name"))
        return True
    except Exception as exc:
        logger.error("monday_connection_failed", error=str(exc))
        return False
