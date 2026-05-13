-- =============================================================================
-- AgAI_27: Quote-to-Invoice Platform
-- Migration 001: Create quote_quotes, quote_orders, quote_audit_log tables
-- Run once in: Supabase Dashboard > SQL Editor
-- =============================================================================


-- -----------------------------------------------------------------------------
-- QUOTE_QUOTES
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quote_quotes (
    -- Identity
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_number        TEXT NOT NULL UNIQUE,           -- e.g. QT-2026-0001

    -- Client
    client_name         TEXT NOT NULL,
    client_id           TEXT,
    contact_name        TEXT,
    contact_email       TEXT,
    contact_phone       TEXT,
    billing_address     TEXT,
    qbo_customer_id     TEXT,                           -- QuickBooks customer ref

    -- Artwork
    artwork_width       NUMERIC(10, 4),
    artwork_height      NUMERIC(10, 4),
    artwork_medium      TEXT,
    artwork_substrate   TEXT,
    artwork_notes       TEXT,

    -- Line items stored as JSONB array
    line_items          JSONB NOT NULL DEFAULT '[]',

    -- Financials
    currency            TEXT NOT NULL DEFAULT 'USD',
    subtotal            NUMERIC(12, 2) NOT NULL DEFAULT 0,
    tax                 NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total               NUMERIC(12, 2) NOT NULL DEFAULT 0,
    notes               TEXT,
    valid_days          INTEGER NOT NULL DEFAULT 30,

    -- Workflow status
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft','sent','approved','rejected','expired','invoiced')),
    pdf_path            TEXT,
    sent_at             TIMESTAMPTZ,
    approved_at         TIMESTAMPTZ,
    rejected_at         TIMESTAMPTZ,
    rejection_reason    TEXT,

    -- QuickBooks sync
    qbo_sync_status     TEXT NOT NULL DEFAULT 'pending'
                            CHECK (qbo_sync_status IN ('pending','synced','failed','skipped')),
    qbo_invoice_id      TEXT,
    qbo_invoice_number  TEXT,
    qbo_synced_at       TIMESTAMPTZ,
    qbo_error           TEXT,

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_quote_quotes_status      ON quote_quotes (status);
CREATE INDEX IF NOT EXISTS idx_quote_quotes_client_name ON quote_quotes (client_name);
CREATE INDEX IF NOT EXISTS idx_quote_quotes_created_at  ON quote_quotes (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quote_quotes_qbo_sync    ON quote_quotes (qbo_sync_status);

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_quote_quotes_updated_at ON quote_quotes;
CREATE TRIGGER set_quote_quotes_updated_at
    BEFORE UPDATE ON quote_quotes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- -----------------------------------------------------------------------------
-- QUOTE_ORDERS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quote_orders (
    -- Identity
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number        TEXT NOT NULL UNIQUE,           -- e.g. ORD-2026-0001
    quote_id            UUID NOT NULL REFERENCES quote_quotes (id),
    quote_number        TEXT NOT NULL,

    -- Client (denormalized for fast reads)
    client_name         TEXT NOT NULL,
    client_id           TEXT,
    contact_name        TEXT,
    contact_email       TEXT,
    contact_phone       TEXT,
    billing_address     TEXT,
    qbo_customer_id     TEXT,

    -- Artwork
    artwork_width       NUMERIC(10, 4),
    artwork_height      NUMERIC(10, 4),
    artwork_medium      TEXT,
    artwork_substrate   TEXT,
    artwork_notes       TEXT,

    -- Line items stored as JSONB array
    line_items          JSONB NOT NULL DEFAULT '[]',

    -- Financials
    currency            TEXT NOT NULL DEFAULT 'USD',
    total               NUMERIC(12, 2) NOT NULL DEFAULT 0,
    notes               TEXT,

    -- Workflow status
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft','confirmed','in_production','completed','cancelled')),

    -- Monday.com sync
    monday_sync_status  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (monday_sync_status IN ('pending','synced','failed','skipped')),
    monday_item_id      TEXT,
    monday_board_id     TEXT,
    monday_synced_at    TIMESTAMPTZ,
    monday_error        TEXT,

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_quote_orders_status      ON quote_orders (status);
CREATE INDEX IF NOT EXISTS idx_quote_orders_quote_id    ON quote_orders (quote_id);
CREATE INDEX IF NOT EXISTS idx_quote_orders_client_name ON quote_orders (client_name);
CREATE INDEX IF NOT EXISTS idx_quote_orders_created_at  ON quote_orders (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quote_orders_monday_sync ON quote_orders (monday_sync_status);

DROP TRIGGER IF EXISTS set_quote_orders_updated_at ON quote_orders;
CREATE TRIGGER set_quote_orders_updated_at
    BEFORE UPDATE ON quote_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- -----------------------------------------------------------------------------
-- QUOTE_AUDIT_LOG
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quote_audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Reference: either a quote_quotes id or quote_orders id
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('quote', 'order')),
    entity_id       UUID NOT NULL,
    entity_number   TEXT NOT NULL,           -- quote_number or order_number

    -- What happened
    agent           TEXT NOT NULL,           -- e.g. qbo_sync_agent, monday_agent
    action          TEXT NOT NULL,           -- e.g. invoice_created, item_created
    from_status     TEXT,
    to_status       TEXT,
    detail          TEXT,
    success         BOOLEAN NOT NULL DEFAULT TRUE,
    error_message   TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_quote_audit_entity_id     ON quote_audit_log (entity_id);
CREATE INDEX IF NOT EXISTS idx_quote_audit_entity_number ON quote_audit_log (entity_number);
CREATE INDEX IF NOT EXISTS idx_quote_audit_timestamp     ON quote_audit_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_quote_audit_success       ON quote_audit_log (success);


-- -----------------------------------------------------------------------------
-- DONE
-- -----------------------------------------------------------------------------
-- Tables created:
--   quote_quotes     - pricing configurator output, quote lifecycle, QBO sync state
--   quote_orders     - confirmed production orders, Monday.com sync state
--   quote_audit_log  - full audit trail for every state transition
-- =============================================================================
