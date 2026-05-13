# agents/monday_agent.py
# AgAI_27 - Quote-to-Invoice Platform
# Orchestrates pushing a confirmed order to Monday.com as a production item.

from __future__ import annotations

from datetime import datetime, timezone
import structlog

from core.models import AgOrder, MondaySyncResult, MondaySyncStatus
from core.database import update_order, insert_quote_audit
from core.config import get_settings
from integrations.monday_client import create_production_item, MondayAPIError

logger = structlog.get_logger(__name__)
settings = get_settings()


class MondayAgent:
    """
    Pushes a confirmed AgOrder to Monday.com as a production item.
    Updates quote_orders table with sync status and audit logs every transition.
    """

    def __init__(self) -> None:
        self.log = logger.bind(agent="monday_agent")

    def sync(self, order: AgOrder) -> MondaySyncResult:
        """
        Main entry point. Call this when an order status moves to 'confirmed'.
        Returns MondaySyncResult with success flag and Monday item details.
        """
        self.log.info("monday_sync_start", order_number=order.order_number)

        board_id = settings.monday_board_id
        if not board_id:
            result = MondaySyncResult(
                order_number=order.order_number,
                success=False,
                error_message="MONDAY_BOARD_ID is not configured.",
            )
            self._mark_failed(order, result)
            return result

        item_name = f"{order.order_number} | {order.client.client_name}"

        try:
            monday_result = create_production_item(
                board_id=board_id,
                item_name=item_name,
                order_number=order.order_number,
                quote_number=order.quote_number,
                client_name=order.client.client_name,
                total=float(order.total),
                currency=order.currency,
                notes=order.notes,
            )

            result = MondaySyncResult(
                order_number=order.order_number,
                success=True,
                monday_item_id=monday_result["monday_item_id"],
                monday_board_id=monday_result["monday_board_id"],
            )

        except MondayAPIError as exc:
            result = MondaySyncResult(
                order_number=order.order_number,
                success=False,
                error_message=str(exc),
            )

        except Exception as exc:
            result = MondaySyncResult(
                order_number=order.order_number,
                success=False,
                error_message=f"Unexpected error: {exc}",
            )

        # Persist sync result back to quote_orders table
        if result.success:
            self._mark_synced(order, result)
        else:
            self._mark_failed(order, result)

        return result

    # ------------------------------------------------------------------
    # Internal state writers
    # ------------------------------------------------------------------

    def _mark_synced(self, order: AgOrder, result: MondaySyncResult) -> None:
        now = datetime.now(timezone.utc).isoformat()

        try:
            update_order(order.order_number, {
                "monday_sync_status": MondaySyncStatus.SYNCED.value,
                "monday_item_id":     result.monday_item_id,
                "monday_board_id":    result.monday_board_id,
                "monday_synced_at":   now,
                "monday_error":       None,
                "status":             "in_production",
                "updated_at":         now,
            })
        except Exception as exc:
            self.log.warning("monday_db_update_failed", error=str(exc))

        try:
            insert_quote_audit({
                "entity_type":   "order",
                "entity_number": order.order_number,
                "agent":         "monday_agent",
                "action":        "monday_item_created",
                "from_status":   "confirmed",
                "to_status":     "in_production",
                "detail":        f"Monday item created. Item ID: {result.monday_item_id}, Board: {result.monday_board_id}",
                "success":       True,
            })
        except Exception as exc:
            self.log.warning("monday_audit_write_failed", error=str(exc))

        self.log.info(
            "monday_sync_success",
            order_number=order.order_number,
            monday_item_id=result.monday_item_id,
        )

    def _mark_failed(self, order: AgOrder, result: MondaySyncResult) -> None:
        now = datetime.now(timezone.utc).isoformat()

        try:
            update_order(order.order_number, {
                "monday_sync_status": MondaySyncStatus.FAILED.value,
                "monday_error":       result.error_message,
                "updated_at":         now,
            })
        except Exception as exc:
            self.log.warning("monday_db_update_failed", error=str(exc))

        try:
            insert_quote_audit({
                "entity_type":   "order",
                "entity_number": order.order_number,
                "agent":         "monday_agent",
                "action":        "monday_item_failed",
                "from_status":   "confirmed",
                "to_status":     None,
                "detail":        f"Monday sync failed: {result.error_message}",
                "success":       False,
                "error_message": result.error_message,
            })
        except Exception as exc:
            self.log.warning("monday_audit_write_failed", error=str(exc))

        self.log.error(
            "monday_sync_failed",
            order_number=order.order_number,
            error=result.error_message,
        )
