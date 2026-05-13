# agents/audit_logger_agent.py
# AgAI_27 - Quote-to-Invoice Platform
# Writes audit trail entries to quote_audit_log for quotes and orders.

import uuid
from datetime import datetime, timezone
from typing import Optional
import structlog

from core.database import insert_quote_audit

logger = structlog.get_logger(__name__)


class AuditLoggerAgent:
    """Writes audit trail entries for quote and order state transitions."""

    def __init__(self) -> None:
        self.log = logger.bind(agent="audit_logger_agent")

    # ------------------------------------------------------------------
    # Quote events
    # ------------------------------------------------------------------

    def log_quote_created(self, quote_number: str) -> dict:
        return self._write(
            entity_type="quote",
            entity_number=quote_number,
            agent="quote_builder",
            action="quote_created",
            from_status=None,
            to_status="draft",
            detail="Quote created from pricing configurator.",
        )

    def log_quote_sent(self, quote_number: str, recipient_email: str) -> dict:
        return self._write(
            entity_type="quote",
            entity_number=quote_number,
            agent="quote_builder",
            action="quote_sent",
            from_status="draft",
            to_status="sent",
            detail=f"Quote PDF sent to {recipient_email}.",
        )

    def log_quote_approved(self, quote_number: str) -> dict:
        return self._write(
            entity_type="quote",
            entity_number=quote_number,
            agent="quote_builder",
            action="quote_approved",
            from_status="sent",
            to_status="approved",
            detail="Quote approved by client.",
        )

    def log_quote_rejected(self, quote_number: str, reason: str) -> dict:
        return self._write(
            entity_type="quote",
            entity_number=quote_number,
            agent="quote_builder",
            action="quote_rejected",
            from_status="sent",
            to_status="rejected",
            detail=f"Quote rejected. Reason: {reason}",
        )

    def log_quote_expired(self, quote_number: str) -> dict:
        return self._write(
            entity_type="quote",
            entity_number=quote_number,
            agent="quote_builder",
            action="quote_expired",
            from_status="sent",
            to_status="expired",
            detail="Quote expired without client response.",
        )

    # ------------------------------------------------------------------
    # QBO sync events
    # ------------------------------------------------------------------

    def log_qbo_sync_success(
        self,
        quote_number: str,
        qbo_invoice_id: str,
        qbo_invoice_number: str,
    ) -> dict:
        return self._write(
            entity_type="quote",
            entity_number=quote_number,
            agent="qbo_sync_agent",
            action="qbo_invoice_created",
            from_status="approved",
            to_status="invoiced",
            detail=f"QBO invoice created. ID: {qbo_invoice_id}, Number: {qbo_invoice_number}",
            success=True,
        )

    def log_qbo_sync_failed(self, quote_number: str, error: str) -> dict:
        return self._write(
            entity_type="quote",
            entity_number=quote_number,
            agent="qbo_sync_agent",
            action="qbo_invoice_failed",
            from_status="approved",
            to_status=None,
            detail="QBO invoice creation failed.",
            success=False,
            error_message=error,
        )

    # ------------------------------------------------------------------
    # Order events
    # ------------------------------------------------------------------

    def log_order_created(self, order_number: str, quote_number: str) -> dict:
        return self._write(
            entity_type="order",
            entity_number=order_number,
            agent="order_manager",
            action="order_created",
            from_status=None,
            to_status="confirmed",
            detail=f"Order created from approved quote {quote_number}.",
        )

    # ------------------------------------------------------------------
    # Monday.com sync events
    # ------------------------------------------------------------------

    def log_monday_sync_success(
        self,
        order_number: str,
        monday_item_id: str,
        monday_board_id: str,
    ) -> dict:
        return self._write(
            entity_type="order",
            entity_number=order_number,
            agent="monday_agent",
            action="monday_item_created",
            from_status="confirmed",
            to_status="in_production",
            detail=f"Monday item created. Item ID: {monday_item_id}, Board: {monday_board_id}",
            success=True,
        )

    def log_monday_sync_failed(self, order_number: str, error: str) -> dict:
        return self._write(
            entity_type="order",
            entity_number=order_number,
            agent="monday_agent",
            action="monday_item_failed",
            from_status="confirmed",
            to_status=None,
            detail="Monday item creation failed.",
            success=False,
            error_message=error,
        )

    # ------------------------------------------------------------------
    # Internal writer
    # ------------------------------------------------------------------

    def _write(
        self,
        entity_type: str,
        entity_number: str,
        agent: str,
        action: str,
        from_status: Optional[str],
        to_status: Optional[str],
        detail: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> dict:
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_type": entity_type,
            "entity_id": None,        # populated by callers who have the UUID
            "entity_number": entity_number,
            "agent": agent,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "detail": detail,
            "success": success,
            "error_message": error_message,
        }

        self.log.info(
            "audit_entry",
            entity_type=entity_type,
            entity_number=entity_number,
            action=action,
            success=success,
        )

        try:
            insert_quote_audit(entry)
        except Exception as exc:
            self.log.warning("audit_db_write_failed", error=str(exc))

        return entry
