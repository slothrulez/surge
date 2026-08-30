# SAFETY_RULES.md — Critical Constraints (Never Violate)

**These rules prevent catastrophic failures. Violating any one could result in:**
- Lost revenue (double charges, missed recoveries)
- Compliance violations (GDPR, RBI regulations)
- Loss of customer trust
- System data corruption

---

## CRITICAL: Error Mapping is Deterministic

**Rule:** Error classification must ONLY use ERROR_CODE_MAPPING lookup table.

**Why:** Wrong classification could recover unpayable failure or skip recoverable one.

**Violation Example:**
```python
# ❌ NEVER do this:
def classify(code, desc):
    return llm.predict_failure_type(desc)  # AI guessing
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
def classify(code, desc):
    key = (code, find_pattern(desc))
    return ERROR_CODE_MAPPING.get(key, FailureType.UNKNOWN)
```

---

## CRITICAL: Policy Checks are Mandatory

**Rule:** No action can execute without passing merchant + customer policy checks.

**Why:** Merchant could lose money if system ignores their configuration.

**Violation Example:**
```python
# ❌ NEVER do this:
if automatic_retry_makes_sense():  # Merchant might have disabled this
    retry_payment()
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
merchant = get_merchant(payment_id)
if not merchant.policy.enabled:
    return
if not merchant.policy.auto_retry_enabled:
    return
if customer.retry_count >= merchant.policy.max_retries:
    return
retry_payment()
```

---

## CRITICAL: Idempotency Keys Prevent Double-Execution

**Rule:** Every action that might be called twice must have an idempotency key.

**Why:** Webhooks retry, requests timeout and retry. Without idempotency, actions duplicate.

**Violation Example:**
```python
# ❌ NEVER do this:
def send_sms(payment_id, phone):
    sms_provider.send(phone, message)
    # If webhook retried, SMS sent twice = double charge
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
def send_sms(payment_id, phone):
    idempotency_key = hash(payment_id + "sms_action")
    
    if db.check_idempotency_key(idempotency_key):
        return db.get_previous_result(idempotency_key)
    
    result = sms_provider.send(phone, message)
    db.record_idempotent_action(idempotency_key, result)
    return result
```

---

## CRITICAL: Audit Logs Capture Everything

**Rule:** Every decision, action, and outcome must be logged with full context.

**Why:** Audit logs prove what happened and why. Enables compliance audits.

**Violation Example:**
```python
# ❌ NEVER do this:
if policy_check_passed:
    execute_action()  # Silent decision, no log
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
audit_log.insert(
    event_type="POLICY_CHECK_PASSED",
    actor="POLICY_ENGINE",
    details={
        "payment_id": payment_id,
        "allowed_actions": list(allowed_actions),
        "reasoning": "Merchant policy allows retry",
    },
    timestamp=now(),
)
execute_action()
```

---

## CRITICAL: No Secrets in Logs or Responses

**Rule:** API keys, auth tokens, payment details NEVER in logs or error messages.

**Why:** Logs are stored, transmitted, visible to multiple people. Secrets must stay secret.

**Violation Example:**
```python
# ❌ NEVER do this:
try:
    razorpay.call(key=RAZORPAY_KEY_SECRET, ...)
except Exception as e:
    logger.error(f"API error: {e}")  # e contains secret
    return {"error": str(e)}  # Secret in response
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
try:
    razorpay.call(key=RAZORPAY_KEY_SECRET, ...)
except RazorpayError as e:
    logger.error(f"Razorpay API error: {e.error_type}")  # Only error type
    audit_log.insert(
        event_type="API_ERROR",
        details={"error_type": e.error_type},  # No secret
    )
    return {"error": "External service error"}  # Generic message
```

---

## CRITICAL: No Money-Related Arbitrary Decisions

**Rule:** Decisions about charging, retrying, or escalating must be based on hardcoded rules or database config, never AI heuristics or thresholds.

**Why:** Customer money is involved. Decisions must be predictable and auditable.

**Violation Example:**
```python
# ❌ NEVER do this:
if confidence_score > llm.predict_optimal_threshold():
    charge_retry_fee()
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
RETRY_COSTS = {
    "AUTO_RETRY": 0,  # Free
    "SMS_CARD_UPDATE": 0,  # Free
    "OFFER_INSTALLMENTS": 0,  # Free (merchant pays)
}

def should_charge_for_action(action_type):
    cost = RETRY_COSTS.get(action_type, 0)
    return cost > 0
```

---

## CRITICAL: Webhook Signature Verification

**Rule:** Every webhook must have valid RAZORPAY_WEBHOOK_SECRET signature before processing.

**Why:** Without verification, attackers could inject fake payment failures.

**Violation Example:**
```python
# ❌ NEVER do this:
@app.post("/webhook/payment.failed")
def webhook(body):
    process_webhook(body)  # No signature check
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
@app.post("/webhook/payment.failed")
def webhook(body, headers):
    signature = headers.get("X-Razorpay-Signature")
    
    if not verify_signature(body, signature, RAZORPAY_WEBHOOK_SECRET):
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    process_webhook(body)
```

---

## CRITICAL: Database Constraints Enforce Rules

**Rule:** If a constraint is critical, enforce it in database schema (CHECK, UNIQUE, FOREIGN KEY). Don't rely on code.

**Why:** Code can have bugs. Database constraints are bulletproof.

**Violation Example:**
```python
# ❌ NEVER do this:
# In code: Check before inserting
if db.check_duplicate(idempotency_key):
    return
db.insert(action)  # But what if two threads insert simultaneously?
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
# In migrations/001_initial_schema.sql:
CREATE TABLE failure_recovery_action (
    action_id UUID PRIMARY KEY,
    idempotency_key VARCHAR UNIQUE,  -- DATABASE prevents duplicate
    ...
);

# In code: Trust the database
try:
    db.insert(FailureRecoveryAction(idempotency_key=key, ...))
except IntegrityError:
    # Database prevented duplicate
    return db.get_existing_action(key)
```

---

## CRITICAL: No Hardcoded Business Logic

**Rule:** Thresholds, limits, percentages must be in config.py or database. Never hardcoded in function logic.

**Why:** Business rules change. Hardcoded values require code changes + redeployment.

**Violation Example:**
```python
# ❌ NEVER do this:
def is_customer_risky(customer):
    if customer.account_age < 1:  # Magic number
        return True
    if customer.failures > 5:  # Magic number
        return True
```

**Correct Implementation:**
```python
# In config.py:
CUSTOMER_RISK_THRESHOLDS = {
    "min_account_age_days": 1,
    "max_failures_before_risk": 5,
}

# In code:
def is_customer_risky(customer):
    min_age = CUSTOMER_RISK_THRESHOLDS["min_account_age_days"]
    max_failures = CUSTOMER_RISK_THRESHOLDS["max_failures_before_risk"]
    
    if customer.account_age < min_age:
        return True
    if customer.failures > max_failures:
        return True
```

---

## CRITICAL: Transactional Consistency

**Rule:** Related database changes must all succeed or all fail together. Never partial updates.

**Why:** Partial updates = data corruption = wrong decisions downstream.

**Violation Example:**
```python
# ❌ NEVER do this:
db.update(payment_failure_event, status="RECOVERED")
# Crash here
db.update(customer_record, success_rate=0.8)  # Partial update
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
with db.transaction():
    db.update(payment_failure_event, status="RECOVERED")
    db.update(customer_record, success_rate=0.8)
    # Atomic: both succeed or both fail
```

---

## CRITICAL: Error Handling is Explicit

**Rule:** Catch specific exceptions. Handle each case. Never silent failures.

**Why:** Silent failures hide bugs. Specific handling proves intent.

**Violation Example:**
```python
# ❌ NEVER do this:
try:
    send_sms(phone, message)
except:
    pass  # Silent failure, customer never knows
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
try:
    send_sms(phone, message)
except SMSProviderTimeout:
    logger.warning("SMS provider timeout, retrying later")
    queue_for_retry(phone, message)
except InvalidPhoneNumber:
    logger.warning("Invalid phone number")
    audit_log.insert(event_type="INVALID_PHONE", details={...})
except Exception as e:
    logger.error(f"Unexpected error: {type(e).__name__}")
    raise
```

---

## CRITICAL: Use Existing Models

**Rule:** All data structures defined in models.py (Phase 0). Use them. Never redefine.

**Why:** Single source of truth. Changes in one place. Type hints work everywhere.

**Violation Example:**
```python
# ❌ NEVER do this:
class PaymentFailure(BaseModel):  # Redefining
    payment_id: str
    error_code: str
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
from models import RazorpayWebhook, PaymentPayload
# Use them as-is
```

---

## CRITICAL: Database-First Approach

**Rule:** Modify database schema only through migration files. Never through ORM auto-creation or raw SQL in code.

**Why:** Migrations are version controlled. You can rollback. Schema is tracked in git.

**Violation Example:**
```python
# ❌ NEVER do this:
Base.metadata.create_all(engine)  # ORM creates tables
```

**Correct Implementation:**
```python
# ✅ ALWAYS do this:
# Create migration: migrations/003_add_column_x.sql
ALTER TABLE table_name ADD COLUMN column_x INT;

# Run migrations:
docker-compose exec postgres psql < migrations/003_add_column_x.sql
```

---

## Summary Checklist

Before shipping ANY code:

- [ ] No LLM decisions on error classification (lookup table only)
- [ ] All actions behind policy check
- [ ] Idempotency keys on all retry-able actions
- [ ] All decisions logged with context
- [ ] No secrets in logs or responses
- [ ] No money decisions without hardcoded logic
- [ ] Webhook signature verified
- [ ] Database constraints enforce critical rules
- [ ] No hardcoded business logic (use config)
- [ ] Related DB changes are transactional
- [ ] Error handling is explicit
- [ ] Using existing models
- [ ] Schema changes via migrations
- [ ] Tests passing

**If ANY checkbox is unchecked, DO NOT COMMIT.**

---

**Violations of these rules could result in revenue loss or compliance issues.**

