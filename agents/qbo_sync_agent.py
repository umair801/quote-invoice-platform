# agents/qbo_sync_agent.py
# AgAI_27 - Quote-to-Invoice Platform
# Orchestrates pushing an approved quote to QuickBooks as a customer Invoice.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import structlog

from core.models import Quote, QBOInvoiceSyncResult, QBOSyncStatus
from core.database import update_quote, insert_quote_audit
from integrations.qbo_invoice_client import create_invoice_in_qbo, QBOInvoiceError

logger = structlog.get_logger(__name__)


class QBOSyncAgent:
    """
    Pushes an approved Quote to QuickBooks Online as a customer Invoice.
    Updates quote_quotes table with sync status and audit logs every transition.
    """

    def __init__(self) -> None:
        self.log = logger.bind(agent="qbo_sync_agent")

    def sync(
        self,
        quote: Quote,
        access_token: Optional[str] = None,
    ) -> QBOInvoiceSyncResult:
        """
        Main entry point. Call this when a quote status moves to 'approved'.
        Returns QBOInvoiceSyncResult with success flag and QBO invoice details.
        """
        self.log.info("qbo_sync_start", quote_number=quote.quote_number)

        try:
            result = create_invoice_in_qbo(quote, access_token=access_token)

        except QBOInvoiceError as exc:
            result = QBOInvoiceSyncResult(
                quote_number=quote.quote_number,
                success=False,
                error_message=str(exc),
            )

        except Exception as exc:
            result = QBOInvoiceSyncResult(
                quote_number=quote.quote_number,
                success=False,
                error_message=f"Unexpected error: {exc}",
            )

        # Persist sync result back to quote_quotes table
        if result.success:
            self._mark_synced(quote, result)
        else:
            self._mark_failed(quote, result)

        return result

    # ------------------------------------------------------------------
    # Internal state writers
    # ------------------------------------------------------------------

    def _mark_synced(self, quote: Quote, result: QBOInvoiceSyncResult) -> None:
        now = datetime.now(timezone.utc).isoformat()

        try:
            update_quote(quote.quote_number, {
                "qbo_sync_status":    QBOSyncStatus.SYNCED.value,
                "qbo_invoice_id":     result.qbo_invoice_id,
                "qbo_invoice_number": result.qbo_invoice_number,
                "qbo_synced_at":      now,
                "qbo_error":          None,
                "status":             "invoiced",
                "updated_at":         now,
            })
        except Exception as exc:
            self.log.warning("qbo_db_update_failed", error=str(exc))

        try:
            insert_quote_audit({
                "entity_type":   "quote",
                "entity_number": quote.quote_number,
                "agent":         "qbo_sync_agent",
                "action":        "qbo_invoice_created",
                "from_status":   "approved",
                "to_status":     "invoiced",
                "detail":        f"QBO invoice created. ID: {result.qbo_invoice_id}, Number: {result.qbo_invoice_number}",
                "success":       True,
            })
        except Exception as exc:
            self.log.warning("qbo_audit_write_failed", error=str(exc))

        self.log.info(
            "qbo_sync_success",
            quote_number=quote.quote_number,
            qbo_invoice_id=result.qbo_invoice_id,
        )

    def _mark_failed(self, quote: Quote, result: QBOInvoiceSyncResult) -> None:
        now = datetime.now(timezone.utc).isoformat()

        try:
            update_quote(quote.quote_number, {
                "qbo_sync_status": QBOSyncStatus.FAILED.value,
                "qbo_error":       result.error_message,
                "updated_at":      now,
            })
        except Exception as exc:
            self.log.warning("qbo_db_update_failed", error=str(exc))

        try:
            insert_quote_audit({
                "entity_type":   "quote",
                "entity_number": quote.quote_number,
                "agent":         "qbo_sync_agent",
                "action":        "qbo_invoice_failed",
                "from_status":   "approved",
                "to_status":     None,
                "detail":        f"QBO sync failed: {result.error_message}",
                "success":       False,
                "error_message": result.error_message,
            })
        except Exception as exc:
            self.log.warning("qbo_audit_write_failed", error=str(exc))

        self.log.error(
            "qbo_sync_failed",
            quote_number=quote.quote_number,
            error=result.error_message,
        )
