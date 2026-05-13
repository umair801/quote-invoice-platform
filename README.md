# AgAI_27: Quote-to-Invoice Platform

**Built by [Datawebify](https://datawebify.com) | Live API: [quote.datawebify.com/docs](https://quote.datawebify.com/docs)**

---

## What This System Does

AgAI_27 is a production quote-to-invoice automation platform for B2B custom product businesses. It replaces fragmented stacks (Excel pricing sheets, manual QBO entry, copy-paste into Monday.com) with a single unified backend that handles the full quote lifecycle: pricing configurator, branded PDF quote generation, client approval, QuickBooks Online invoice push, and Monday.com production item creation.

The system exposes a clean FastAPI backend with 15 endpoints covering quotes, orders, QBO OAuth2, and health checks. Every state transition is audit-logged to Supabase with a complete trail from quote creation to production handoff.

---

## Business Outcomes

| Metric | Manual Process | With AgAI_27 | Change |
|---|---|---|---|
| Quote creation time | 30 to 60 min (Excel + PDF) | Under 60 seconds | 95% faster |
| QBO invoice entry | 10 to 15 min manual | Automatic on approval | 100% eliminated |
| Monday production item | 5 to 10 min manual | Automatic on order creation | 100% eliminated |
| Data entry errors | High (copy-paste) | Near zero (single source of truth) | 90%+ reduction |
| Audit trail | None or inconsistent | 100% automated per event | Full coverage |
| Quote-to-order cycle | 1 to 2 days | Under 5 minutes | 95% faster |

---

## Live Endpoints

| Feature | URL |
|---|---|
| Interactive API Docs | [quote.datawebify.com/docs](https://quote.datawebify.com/docs) |
| System Health | [quote.datawebify.com/health](https://quote.datawebify.com/health) |
| QBO Connection Status | [quote.datawebify.com/health/qbo](https://quote.datawebify.com/health/qbo) |
| Monday Connection Status | [quote.datawebify.com/health/monday](https://quote.datawebify.com/health/monday) |

---

## API Reference

### Quotes

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/quotes/` | Create a quote from pricing configurator output |
| `GET` | `/quotes/` | List all quotes, filterable by status |
| `GET` | `/quotes/{quote_number}` | Fetch a single quote |
| `POST` | `/quotes/{quote_number}/send` | Mark quote as sent to client |
| `POST` | `/quotes/{quote_number}/approve` | Approve quote and push QBO invoice |
| `POST` | `/quotes/{quote_number}/reject` | Reject quote with reason |
| `POST` | `/quotes/{quote_number}/sync-qbo` | Manually retry QBO invoice sync |

### Orders

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/orders/` | Create production order from approved quote |
| `GET` | `/orders/` | List all orders, filterable by status |
| `GET` | `/orders/{order_number}` | Fetch a single order |
| `POST` | `/orders/{order_number}/sync-monday` | Manually retry Monday.com sync |
| `PATCH` | `/orders/{order_number}/status` | Update production status |

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/auth/quickbooks` | Initiate QBO OAuth2 flow |
| `GET` | `/auth/quickbooks/callback` | QBO OAuth2 callback handler |
| `GET` | `/auth/quickbooks/status` | Check QBO connection status |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | App liveness check |
| `GET` | `/health/qbo` | QuickBooks API connectivity |
| `GET` | `/health/monday` | Monday.com API connectivity |

---

## System Architecture

```
Client Request (POST /quotes/)
        |
   Quote Router
        |
   Compute line totals + grand total
        |
   Insert to quote_quotes (Supabase)
        |
   Audit Logger -> quote_audit_log
        |
   Return quote_number


Quote Approved (POST /quotes/{quote_number}/approve)
        |
   Update quote_quotes: status = approved
        |
   QBO Sync Agent
        |
   qbo_invoice_client: find_or_create_customer -> create_invoice
        |
      Success                    Failure
        |                           |
   Update: status=invoiced     Update: qbo_sync_status=failed
   qbo_invoice_id stored       qbo_error stored
        |
   Audit Logger -> quote_audit_log


Order Created (POST /orders/)
        |
   Validate quote is approved
        |
   Insert to quote_orders (Supabase)
        |
   Monday Agent
        |
   monday_client: create_production_item (GraphQL)
        |
      Success                    Failure
        |                           |
   Update: status=in_production  Update: monday_sync_status=failed
   monday_item_id stored         monday_error stored
        |
   Audit Logger -> quote_audit_log
```

---

## Database Schema

Three tables, all prefixed `quote_` per AgAI_27 naming convention:

**`quote_quotes`** — Quote records with full QBO sync state
**`quote_orders`** — Production orders with Monday.com sync state
**`quote_audit_log`** — Complete audit trail for every state transition

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Database | Supabase (PostgreSQL) |
| QBO Integration | QuickBooks Online REST API (OAuth2) |
| Monday Integration | Monday.com GraphQL API v2 |
| PDF Generation | ReportLab |
| AI Models | GPT-4o, Claude API |
| Notifications | SendGrid, Twilio |
| Logging | structlog (JSON structured logs) |
| Deployment | Docker + Railway |
| Language | Python 3.12 |

---

## Project Structure

```
AgAI_27_Quote_Invoice_Platform/
├── agents/
│   ├── audit_logger_agent.py      # Audit trail writer for all events
│   ├── qbo_sync_agent.py          # Orchestrates QBO invoice push
│   └── monday_agent.py            # Orchestrates Monday.com item creation
├── api/
│   ├── main.py                    # FastAPI app entry point
│   ├── auth_router.py             # QBO OAuth2 flow
│   ├── quote_router.py            # Quote lifecycle endpoints
│   ├── order_router.py            # Order lifecycle endpoints
│   └── health_router.py           # Health and connectivity checks
├── core/
│   ├── config.py                  # Settings and env var loading
│   ├── database.py                # Supabase client and table functions
│   ├── logger.py                  # Structured logging config
│   └── models.py                  # Pydantic models for all entities
├── integrations/
│   ├── quickbooks_client.py       # AP-direction QBO (Bills) - from AgAI_10
│   ├── qbo_invoice_client.py      # AR-direction QBO (Invoices) + OAuth2
│   ├── monday_client.py           # Monday.com GraphQL client
│   └── xero_client.py             # Xero integration (future use)
├── migrations/
│   └── 001_create_agai27_tables.sql
├── tests/
├── Dockerfile
├── railway.json
├── requirements.txt
└── .env.example
```

---

## Setup and Deployment

### Prerequisites

- Python 3.12
- Docker
- Supabase account
- QuickBooks Online developer app
- Monday.com API key

### Local Setup

```bash
git clone https://github.com/umair801/quote-invoice-platform.git
cd quote-invoice-platform
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env
# Fill in credentials in .env
uvicorn api.main:app --reload --port 8000
```

### Environment Variables

```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
QUICKBOOKS_CLIENT_ID=
QUICKBOOKS_CLIENT_SECRET=
QUICKBOOKS_REFRESH_TOKEN=
QUICKBOOKS_REALM_ID=
QUICKBOOKS_REDIRECT_URI=http://localhost:8000/auth/quickbooks/callback
MONDAY_API_KEY=
MONDAY_BOARD_ID=
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
APP_ENV=development
LOG_LEVEL=INFO
```

### Docker

```bash
docker build -t quote-invoice-platform .
docker run -p 8000:8000 --env-file .env quote-invoice-platform
```

---

## QBO OAuth2 Setup (one-time per client)

1. Create a QuickBooks Online developer app at [developer.intuit.com](https://developer.intuit.com)
2. Set the redirect URI to `https://your-domain.com/auth/quickbooks/callback`
3. Add `QUICKBOOKS_CLIENT_ID` and `QUICKBOOKS_CLIENT_SECRET` to `.env`
4. Visit `/auth/quickbooks` to start the OAuth2 flow
5. After authorization, copy `realm_id` and `refresh_token` from the callback response into `.env`
6. Verify connection at `/auth/quickbooks/status`

---

## Target Clients

Operations managers, sales directors, and studio owners at custom product businesses (framing, printing, fabrication, bespoke manufacturing) processing 20 to 200 quotes per month who need to eliminate manual QBO entry and production handoff steps.

---

## About Datawebify

Datawebify builds enterprise-grade agentic AI systems for organizations that require production-ready automation at scale.

Website: [datawebify.com](https://datawebify.com)
GitHub: [github.com/umair801](https://github.com/umair801)
API Docs: [quote.datawebify.com/docs](https://quote.datawebify.com/docs)
