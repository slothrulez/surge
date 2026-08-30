# Project Specification — Payment Failure Auto-Responder

**Version:** 1.0  
**Last Updated:** 2024-01-15  
**Status:** Phases 0-1 Complete, Phase 2+ Ready to Build

---

## System Purpose

Detect failed Razorpay payments, classify why they failed, and execute deterministic recovery actions (retry, SMS, installments, escalation) while maintaining complete audit trails.

**Core Principle:** Never take action without explicit permission from merchant + customer policies.

---

## System Components

### Phase 0-1: Foundation (COMPLETE) ✅

#### Models (Phase 0)
- All data structures defined in Pydantic models
- All enums for failure types, action types, status tracking
- Webhook payload structure matches Razorpay exactly
- Diagnosis output structure defined
- Audit log entry structure defined

#### Configuration (Phase 0)
- Error code → failure type mapping (deterministic)
- Retry strategy configuration
- Merchant policy defaults
- Customer eligibility rules
- SMS throttling rules
- Safety constraints baked into configuration

#### Project Setup (Phase 1)
- FastAPI application scaffolding
- Database schema with 10 tables
- Docker setup for local development
- Health check endpoint
- Stub endpoints for all phases
- Logging infrastructure

### Phase 2: Database Layer (20 tasks)

**Deliverables:**
- SQLAlchemy ORM models mapping to schema
- CRUD functions for all tables:
  - `insert_payment_failure_event()`
  - `get_payment_failure_by_id()`
  - `update_failure_status()`
  - `insert_recovery_action()`
  - `get_recovery_actions_for_failure()`
  - `log_audit_event()`
  - `check_idempotency()`
  - Plus 13 more CRUD operations

**Constraints:**
- All database operations must be transactional
- All inserts must update audit_log
- All updates must check idempotency
- No business logic in queries (just data access)

### Phase 3: Webhook Receiver (8 tasks)

**Input:** Razorpay `payment.failed` webhook

**Processing:**
1. Verify webhook signature (CRITICAL)
2. Parse webhook payload
3. Check for duplicate (idempotency)
4. Extract payment data
5. Queue for async processing

**Output:** Acknowledgment + payment_failure_event in database

**Constraints:**
- No processing without signature verification
- Duplicate webhooks must be skipped (not processed twice)
- Must queue within 5 seconds (non-blocking response)

### Phase 4: Diagnosis Engine (18 tasks)

**Input:** Payment failure event

**Processing:**
1. Parse Razorpay error code and description
2. Map to FailureType using deterministic lookup table (NOT AI)
3. Assign confidence score (0-1)
4. Determine if recoverable (some types never recoverable)
5. Return diagnosis result

**Output:** DiagnosisResult with failure_type + confidence

**Constraints:**
- Error code mapping is lookup table only (no AI guessing)
- FRAUD_FLAG + ACCOUNT_CLOSED always marked unrecoverable
- Confidence scores are deterministic (not LLM-based)
- Must handle unknown error codes gracefully (default: UNKNOWN with confidence 0.5)

### Phase 5: Policy Engine (18 tasks)

**Input:** Payment + customer + merchant policy

**Processing:**
1. Check if failure type is in merchant's allowed_failure_types
2. Check if customer is high-risk (if so, restrict actions)
3. Verify action would not violate daily SMS limit
4. Verify action within retry limits
5. Return eligible actions

**Output:** List of allowed ActionTypes

**Constraints:**
- Merchant policy is absolute (no override)
- Customer policy further restricts (more conservative)
- SMS limit is per-customer per-day (not global)
- Retry limit is per-payment (not per-merchant)
- Policy checks are logged

### Phase 6: Strategy Selector (12 tasks)

**Input:** Eligible actions + payment details + customer history

**Processing:**
1. Score each eligible action (how likely to recover?)
2. Rank by score
3. Select top option
4. Return strategy result with reasoning

**Output:** StrategySelectionResult (selected_action + scores)

**Constraints:**
- Only considers eligible actions (never suggests blocked action)
- Scoring is based on:
  - Action effectiveness (historical success rate)
  - Payment amount
  - Customer history
  - Temporal factors
- Scoring weights are configurable (in config.py)
- Never hardcode action preference (use config)

### Phase 7: Action Executor (20 tasks)

**Input:** Selected action + payment details

**Processing:**
1. Validate action prerequisites
2. Execute action (SMS, retry, installments, etc.)
3. Record execution result
4. Update failure status
5. Log outcome

**Output:** ActionExecutionResult (success + status + message)

**Sub-components:**
- **Auto-Retry:** Call Razorpay API to retry payment
- **SMS Notification:** Send card update link via SMS
- **Installments:** Offer EMI option via SMS + callback
- **Escalation:** Create support ticket for manual review

**Constraints:**
- Must use idempotency keys (no double-execution)
- Must check retry limit before retry
- Must check SMS limit before SMS
- Must log all external API calls
- Must gracefully handle external service failures

### Phase 8: External APIs (15 tasks)

**Integrations:**
1. **Razorpay API** — Retry payment, fetch details
2. **SMS Provider** — Send SMS (Twilio/MSG91/Razorpay)
3. **Support Ticketing** — Create escalations (manual system)
4. **Customer CRM** — Log customer interaction (optional)

**Constraints:**
- All API calls must have timeouts
- All API calls must be retryable
- All API failures must be logged
- No sensitive data in API payloads (payment details, auth tokens)
- Fallback to escalation if external API fails

### Phase 9: Outcome Tracking (12 tasks)

**Tracks:**
- SMS delivery status (sent/delivered/failed/clicked)
- Retry results (success/failed)
- Installment acceptance (yes/no/timeout)
- Escalation resolution (resolved/pending/rejected)

**Updates:**
- Marks payment as recovered (if outcome is success)
- Updates customer success rate
- Records recovery amount
- Triggers outcome callbacks

**Constraints:**
- Outcome recorded only after confirmed (not just attempted)
- Success marked only when payment is actually processed
- Failed outcomes still logged (for metrics)
- Callbacks are idempotent (can be called multiple times)

### Phase 10: Metrics & Reporting (15 tasks)

**Metrics Tracked:**
1. Overall recovery rate (recovered / failed)
2. Recovery rate by failure type
3. Recovery rate by action type
4. SMS delivery rate
5. Revenue recovered (in INR)
6. Average recovery time
7. Escalation rate

**Targets (Success Criteria):**
- Overall: 60-70% recovery
- Card Expired: 75%
- Insufficient Balance: 70%
- Timeout: 95%
- Escalation rate: < 20%

**Endpoints:**
- `GET /metrics/recovery-rate`
- `GET /metrics/by-failure-type`
- `GET /metrics/by-action-type`
- `GET /metrics/revenue-recovered`

**Constraints:**
- Metrics are read-only (calculated, not stored)
- Calculations use actual outcome data (not estimates)
- Time windows are configurable
- Metrics API is public (safe to expose)

### Phase 11: Monitoring & Logging (10 tasks)

**Logging:**
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Never log: API keys, payment tokens, sensitive data
- Always log: Decision context (why this action?)

**Monitoring:**
- Alert on high failure rate
- Alert on high escalation rate
- Alert on external API failures
- Alert on database connection issues

**Constraints:**
- Logs are queryable (searchable by payment_id)
- Log retention is configurable
- No logs exposed to end users
- All logs go to centralized sink (ELK, CloudWatch, etc.)

### Phase 12: Integration Tests (12 tasks)

**Test Coverage:**
- Webhook receiver (valid + invalid + duplicate)
- Diagnosis engine (all error types)
- Policy engine (merchant + customer policies)
- Strategy selector (all action types)
- Action executor (success + failure scenarios)
- Database layer (CRUD operations)
- Idempotency (duplicate requests)

**Constraints:**
- Tests use isolated test database
- Tests are deterministic (no flakiness)
- Tests cover happy path + error paths
- Tests verify audit log entries created

### Phase 13: Configuration (8 tasks)

**Endpoints:**
- `GET /config/merchant/{id}` — Retrieve merchant policy
- `POST /config/merchant/{id}` — Update merchant policy
- `GET /config/customer/{id}` — Retrieve customer risk score
- `POST /config/sms-template` — Update SMS templates

**Configuration Items:**
- Merchant policy (retry config, daily SMS limit)
- SMS templates (customizable text)
- External API credentials
- Feature flags (enable/disable actions)
- Scoring weights (for strategy selector)

**Constraints:**
- Only authenticated admins can update config
- Policy changes don't affect in-flight payments
- Feature flags are hot-reloadable (no restart needed)
- All config changes are logged

### Phase 14: Documentation (8 tasks)

**Deliverables:**
1. **API.md** — Complete OpenAPI/Swagger docs
2. **RUNBOOK.md** — How to operate in production
3. **TROUBLESHOOTING.md** — Common issues + fixes
4. **ARCHITECTURE.md** — System design overview
5. **DEPLOYMENT.md** — How to deploy (Docker, Kubernetes)
6. **SECURITY.md** — Security model + best practices

---

## Data Models (Already Defined in Phase 0)

### Request Models
- `RazorpayWebhook` — Incoming webhook from Razorpay
- `ActionExecutionRequest` — Request to execute action
- `MerchantPolicy` — Merchant configuration

### Response Models
- `HealthCheckResponse` — Health endpoint
- `DiagnosisResult` — Diagnosis output
- `StrategySelectionResult` — Strategy selector output
- `ActionExecutionResult` — Action executor output
- `FailureRecoveryStatus` — Status of recovery attempt

### Enums (Already Defined)
- `FailureType` — 10 types (CARD_EXPIRED, INSUFFICIENT_BALANCE, etc.)
- `ActionType` — 4 actions (AUTO_RETRY, SMS_CARD_UPDATE, OFFER_INSTALLMENTS, ESCALATE_MANUAL)
- `RecoveryStatus` — State machine (PENDING, DIAGNOSED, POLICY_CHECK_PASSED, etc.)

---

## Database Tables (Already Defined in Phase 1)

10 tables with full schema:

1. **payment_failure_event** — Core failure tracking
2. **failure_recovery_action** — Each action attempt
3. **audit_log** — Complete audit trail
4. **idempotency_key** — Prevent double-execution
5. **merchant_policy** — Merchant configuration
6. **customer_record** — Customer history + risk score
7. **sms_delivery_tracking** — SMS delivery status
8. **outcome_record** — Outcome tracking
9. **support_escalation** — Manual escalations
10. **diagnosis_cache** — Cache diagnosis results

---

## Safety Rules (Enforced)

### Rule 1: Error Mapping is Deterministic
```python
# ✅ Lookup table only
ERROR_CODE_MAPPING = {
    ("BAD_REQUEST_ERROR", "Card has expired"): FailureType.CARD_EXPIRED,
}

# ❌ Never use AI for this
def classify_error(code, description):
    # Use LLM...
```

### Rule 2: Policy Checks are Mandatory
```python
# ✅ Check before every action
if not policy_engine.is_eligible(failure, merchant, customer):
    raise PolicyViolation()
action_executor.execute(action)

# ❌ Never skip policy check
action_executor.execute(action)  # What if merchant disabled this?
```

### Rule 3: Idempotency Keys are Required
```python
# ✅ Every action has idempotency key
idempotency_key = hash(payment_id + action_type)
if not db.check_idempotency(idempotency_key):
    db.insert_action(idempotency_key, ...)
    execute_action()

# ❌ Never execute without checking
execute_action()  # What if called twice?
```

### Rule 4: Audit Logs are Comprehensive
```python
# ✅ Log every decision
audit_log.insert(
    event_type="POLICY_CHECK_PASSED",
    actor="POLICY_ENGINE",
    details={"failure_id": "...", "allowed_actions": [...]},
)

# ❌ Never have silent decisions
if is_eligible:
    execute_action()  # No log
```

### Rule 5: Secrets Never in Logs
```python
# ✅ Database schema prevents this
CREATE TABLE audit_log (
    details JSONB NOT NULL,
    CHECK (details::text NOT LIKE '%RAZORPAY_KEY_SECRET%'),
);

# ❌ Never log secrets
logger.error(f"API Key: {RAZORPAY_KEY_SECRET}")
```

### Rule 6: No Arbitrary Thresholds
```python
# ✅ All thresholds in config
CUSTOMER_POLICY_RULES = {
    "daily_sms_limit_per_customer": 3,  # Configurable
    "max_retries": 5,
}

# ❌ Never hardcode
if customer_attempts > 5:  # Where did 5 come from?
    escalate()
```

---

## API Endpoints

### Phase 1 (Complete)
- `GET /health` — Health check

### Phase 3 (Webhook Receiver)
- `POST /webhook/payment.failed` — Receive Razorpay webhook

### Phase 10 (Metrics)
- `GET /metrics/recovery-rate` — Overall recovery rate
- `GET /metrics/by-failure-type` — Per-type breakdown
- `GET /metrics/revenue-recovered` — Total recovered

### Phase 13 (Configuration)
- `GET /config/merchant/{id}` — Retrieve merchant policy
- `POST /config/merchant/{id}` — Update merchant policy

---

## Deployment Model

### Local Development
- Docker Compose (PostgreSQL + Redis + API)
- `.env` file with test credentials
- Hot-reload for development

### Production (Kubernetes)
- Helm chart (to be created in Phase 14)
- PostgreSQL on managed cloud DB
- Redis on managed cache service
- FastAPI on Kubernetes cluster
- Monitoring with Prometheus + Grafana

---

## Testing Strategy

### Unit Tests (Phase 12)
- Each function tested in isolation
- Mock external dependencies
- Test all error paths

### Integration Tests (Phase 12)
- End-to-end workflow tests
- Real database (test instance)
- Real Redis (test instance)

### Load Tests (Optional)
- Webhook receiver throughput
- Database query performance
- API response times

---

## Success Metrics

By end of Phase 14, this system should:

✅ Recover 60-70% of failed payments  
✅ Recover 75% of card-expired failures  
✅ Recover 95% of timeout failures  
✅ Maintain < 20% escalation rate  
✅ Process webhooks in < 100ms  
✅ Log every decision with full context  
✅ Have zero data loss (transactional consistency)  
✅ Support 100+ merchants simultaneously  
✅ Be fully documented and runnable  

---

## Known Constraints

1. **Razorpay Test Mode Only** — Initially built for test mode, extend to production gradually
2. **Single SMS Provider** — Currently Twilio, extensible to others
3. **Manual Escalation** — Escalations go to support queue (no auto-resolution)
4. **No Real-Time Dashboard** — Metrics API only, no live web UI (Phase 14+)
5. **Merchants Set Policies** — No enforcement of "good" policies by system

---

## Next Phase

**Phase 2: Database Layer** (20 tasks, 3-4 days)
- Create SQLAlchemy ORM models
- Create CRUD functions
- Test all database operations

Reference: `INSTRUCTION.md` for step-by-step guidance.

---

**For implementation details, see RULES.md and INSTRUCTION.md**

