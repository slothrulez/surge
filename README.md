# Payment Failure Auto-Responder

A Razorpay-native system that detects failed payments, diagnoses why they failed, executes bounded recovery actions, and maintains an auditable trail.

**Reference:** Complete blueprint: `./docs/BLUEPRINT.md`

---

## Quick Start (5 minutes)

### Prerequisites
- Docker & Docker Compose
- Razorpay test mode credentials
- SMS provider account (optional for dev)

### Setup

1. **Clone and enter directory**
   ```bash
   cd payment-recovery-system
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Add Razorpay credentials to `.env`**
   ```env
   RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXX
   RAZORPAY_KEY_SECRET=XXXXXXXXXXXXX
   RAZORPAY_WEBHOOK_SECRET=XXXXXXXXXXXXX
   ```

4. **Start all services**
   ```bash
   docker-compose up
   ```

5. **Verify health**
   ```bash
   curl http://localhost:8000/health
   ```

   Expected response:
   ```json
   {
     "status": "healthy",
     "timestamp": "2024-01-01T00:00:00",
     "version": "1.0.0"
   }
   ```

---

## Project Structure

```
payment-recovery-system/
├── main.py                    # FastAPI application (Phase 1)
├── models.py                  # Pydantic models (Phase 0)
├── config.py                  # Configuration & enums (Phase 0)
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container image
├── docker-compose.yml         # Local development setup
├── .env.example              # Environment template
│
├── migrations/
│   └── 001_initial_schema.sql # Database schema (Phase 2)
│
├── src/                       # Source code (to be created)
│   ├── detection/             # Phase 3: Detection engine
│   ├── diagnosis/             # Phase 4: Diagnosis engine
│   ├── policy/                # Phase 5: Policy engine
│   ├── strategy/              # Phase 6: Strategy selector
│   ├── actions/               # Phase 7: Action executor
│   ├── external/              # Phase 8: External integrations
│   ├── outcomes/              # Phase 9: Outcome tracking
│   ├── metrics/               # Phase 10: Metrics & reporting
│   ├── monitoring/            # Phase 11: Logging & monitoring
│   └── database/              # Database layer (Task 31-43)
│
├── tests/                     # Test suite (Phase 12)
│   ├── test_diagnosis.py
│   ├── test_policy.py
│   └── test_integration.py
│
└── docs/
    ├── BLUEPRINT.md           # Full system specification
    ├── API.md                 # API reference
    └── RUNBOOK.md             # Operational runbook
```

---

## Architecture Overview

```
Razorpay pays customer
        ↓
[If successful] → order confirmed, no action
        ↓
[If failed] → payment.failed webhook sent
        ↓
[Webhook Receiver] → receive, verify signature, deduplicate
        ↓
[Detection Engine] → is this actually a failure?
        ↓
[Diagnosis Engine] → what type of failure? (parse + classify)
        ↓
[Policy Engine] → is recovery allowed? (merchant + customer policy)
        ↓
[Strategy Selector] → which action is most likely to work?
        ↓
[Action Executor] → send SMS, retry, create EMI, escalate
        ↓
[Audit Logger] → log every decision
        ↓
[Outcome Tracker] → did it work? update status
        ↓
[Metrics Dashboard] → report recovery rate + revenue
```

**Reference:** Blueprint Part 2 (System Architecture)

---

## Data Models

All data structures are defined in `models.py` following the blueprint exactly:

- **FailureType** — Classification of payment failures (CARD_EXPIRED, INSUFFICIENT_BALANCE, etc.)
- **ActionType** — Recovery actions (AUTO_RETRY, SMS_CARD_UPDATE, OFFER_INSTALLMENTS, ESCALATE_MANUAL)
- **RecoveryStatus** — State machine for each failure
- **DiagnosisResult** — Output from diagnosis engine
- **AuditLogEntry** — Complete audit trail
- **IdempotencyKey** — Prevent double-execution

**Reference:** Blueprint Part 0 (Interfaces & Config)

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in:

**Critical (must set):**
- `RAZORPAY_KEY_ID` — Test mode key from Razorpay dashboard
- `RAZORPAY_KEY_SECRET` — Test mode secret
- `RAZORPAY_WEBHOOK_SECRET` — Webhook secret for signature verification

**Optional (defaults provided):**
- `SMS_PROVIDER` — "twilio", "msg91" (default: "twilio")
- `SMS_ACCOUNT_SID`, `SMS_AUTH_TOKEN`, `SMS_FROM_NUMBER` — SMS provider creds
- `LOG_LEVEL` — "DEBUG", "INFO", "WARNING", "ERROR" (default: "INFO")
- `ENABLE_AUTO_RETRY` — true/false (default: true)
- `ENABLE_SMS` — true/false (default: true)
- `ENABLE_INSTALLMENTS` — true/false (default: true)

### Merchant Policy

Merchants can configure recovery behavior via `POST /config/merchant/{merchant_id}`:

```json
{
  "recovery_config": {
    "enabled": true,
    "allowed_failure_types": [
      "INSUFFICIENT_BALANCE",
      "CARD_EXPIRED",
      "TIMEOUT"
    ],
    "retry_config": {
      "max_retries": 5,
      "retry_delays_seconds": [60, 300, 900, 3600, 86400]
    },
    "sms_enabled": true,
    "installments_enabled": true,
    "daily_sms_limit_per_customer": 3
  }
}
```

**Reference:** Blueprint lines 207-232 (Merchant Policy)

---

## Safety Rules

### Absolute Rules (Cannot Be Broken)

These are enforced at the code level, not by policy:

1. ✅ **Webhook signature verification** — Every webhook verified before processing
2. ✅ **Idempotency** — No payment retried twice (checked before execution)
3. ✅ **Audit trail** — Every decision logged with full context
4. ✅ **Policy enforcement** — Merchant + customer policy checked before action
5. ✅ **Retry limits** — Never exceed `max_retries` configured
6. ✅ **SMS throttle** — Never send > `daily_sms_limit_per_customer` SMS to one customer
7. ✅ **No secrets in logs** — API keys never exposed

### What Must Never Happen

- ❌ LLM decides whether to charge customer
- ❌ LLM overrides policy check
- ❌ LLM marks payment successful without verification
- ❌ Action executed twice (idempotency bypassed)
- ❌ Decision made without audit log entry
- ❌ SMS sent without consent record
- ❌ Retry attempted without checking retry limit
- ❌ Secret exposed in logs

**Reference:** Blueprint Part 8 (Safety Rules, lines 1403-1422)

---

## Phases & Implementation Status

| Phase | Component | Status | Tasks |
|-------|-----------|--------|-------|
| **0** | Interfaces & Config | ✅ Complete | 15 |
| **1** | Project Setup | ✅ Complete | 8 |
| **2** | Database Layer | 📝 Next | 20 |
| **3** | Webhook Receiver | ⏳ Queued | 8 |
| **4** | Diagnosis Engine | ⏳ Queued | 18 |
| **5** | Policy Engine | ⏳ Queued | 18 |
| **6** | Strategy Selector | ⏳ Queued | 12 |
| **7** | Action Executor | ⏳ Queued | 20 |
| **8** | External APIs | ⏳ Queued | 15 |
| **9** | Outcome Tracking | ⏳ Queued | 12 |
| **10** | Metrics & Reporting | ⏳ Queued | 15 |
| **11** | Monitoring & Logging | ⏳ Queued | 10 |
| **12** | Integration Tests | ⏳ Queued | 12 |
| **13** | Configuration | ⏳ Queued | 8 |
| **14** | Documentation | ⏳ Queued | 8 |

---

## Endpoints (Phase 1 - Health Check Only)

### Health Check
```
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "version": "1.0.0"
}
```

### Webhook Receiver (Phase 3)
```
POST /webhook/payment.failed

Header: X-Razorpay-Signature: <signature>

Body: <Razorpay webhook payload>

Response: { "received": true, "event_id": "...", "timestamp": "..." }
```

### Metrics (Phase 10)
```
GET /metrics/recovery-rate
GET /metrics/by-failure-type
GET /metrics/revenue-recovered
```

---

## Database

### Schema

All tables defined in `migrations/001_initial_schema.sql`:

- `payment_failure_event` — Each detected failure
- `failure_recovery_action` — Each recovery attempt
- `audit_log` — Complete audit trail
- `idempotency_key` — Prevent double-execution
- `merchant_policy` — Merchant configuration
- `customer_record` — Customer history
- `sms_delivery_tracking` — SMS outcomes
- `outcome_record` — General outcome tracking
- `support_escalation` — Manual escalations
- `diagnosis_cache` — Diagnosis result cache

### Initialization

Migrations run automatically on `docker-compose up` via the PostgreSQL container.

To manually run migrations:
```bash
docker-compose exec postgres psql -U postgres -d payment_recovery -f /docker-entrypoint-initdb.d/001_initial_schema.sql
```

---

## Logging

All decisions logged with full context (Blueprint Part 8).

Log levels:
- `DEBUG` — Detailed tracing (development only)
- `INFO` — Standard operation logs
- `WARNING` — Unusual conditions
- `ERROR` — Failures

**Never logged:**
- API keys
- Customer payment details
- Sensitive user data

---

## Testing

All tests require Phase implementations.

Currently no tests (Phase 12 pending).

```bash
# Run all tests (when available)
pytest

# Run specific test
pytest tests/test_diagnosis.py

# Run with coverage
pytest --cov=src tests/
```

---

## Deployment

### Local (Docker Compose)
```bash
docker-compose up
```

### Production (Kubernetes)
- TODO: Create Helm chart
- TODO: Add monitoring/alerting config
- TODO: Add load balancing config

---

## Metrics & Success Criteria

**Target metrics (Blueprint Part 10):**

| Metric | Target |
|--------|--------|
| Overall recovery rate | 60-70% |
| Recovery: INSUFFICIENT_BALANCE | 70% |
| Recovery: CARD_EXPIRED | 75% |
| Recovery: TIMEOUT | 95% |
| Escalation rate | <20% |
| Average recovery time | <2 hours |
| SMS delivery rate | >95% |

---

## Troubleshooting

### Webhook not received
1. Check `RAZORPAY_WEBHOOK_SECRET` is correct
2. Verify webhook URL is publicly accessible
3. Check Razorpay dashboard > Webhook Settings

### Database connection error
```
docker-compose logs postgres
docker-compose exec postgres pg_isready
```

### Redis connection error
```
docker-compose logs redis
docker-compose exec redis redis-cli ping
```

### Signature verification failing
- Ensure `RAZORPAY_WEBHOOK_SECRET` matches Razorpay dashboard
- Check webhook request headers include `X-Razorpay-Signature`

---

## References

- **Full Blueprint:** `./docs/BLUEPRINT.md`
- **API Documentation:** `./docs/API.md` (to be created in Phase 14)
- **Razorpay Docs:** https://razorpay.com/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com

---

## License

Proprietary — Razorpay Buildathon Reference Implementation

---

## Next Steps

1. ✅ Phase 0: Interfaces & Config (COMPLETE)
2. ✅ Phase 1: Project Setup (COMPLETE)
3. 📝 **Phase 2: Database Layer** (START HERE)
   - Task 31: `insert_payment_failure_event()`
   - Task 32: `get_payment_failure_by_id()`
   - ... (20 tasks total)
