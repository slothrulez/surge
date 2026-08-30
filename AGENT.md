# AGENT.md — How to Work With AI Agents on This Project

**Use this guide when delegating work to AI (Claude, ChatGPT, etc.)**

---

## Never Give Full Blueprint

❌ **DO NOT provide:** `docs/BLUEPRINT.md` (internal reasoning)

✅ **DO provide:**
- `SPEC.md` — What to build
- `RULES.md` — How to build it
- `INSTRUCTION.md` — Step-by-step for current phase
- Current task from `MASTER_TASK_CHECKLIST.md`

---

## Prompt Template for AI Agent

```
You are building Phase [N] of a payment recovery system.

**Specification:** [Paste SPEC.md - Phase [N] section]

**Rules to Follow:** [Paste RULES.md]

**Your Current Task:**
Phase [N], Task [X]: [Task description from MASTER_TASK_CHECKLIST.md]

**Current Status:**
- [What exists already]
- [What you're building now]

**Success Criteria:**
[From SPEC.md section]

**Constraints:**
[From SAFETY_RULES.md relevant sections]

Build this following all rules exactly. If you think a rule should be broken, ask first.
```

---

## What NOT to Tell AI

❌ Don't mention:
- Blueprint file contents
- Internal policy decisions
- Why certain thresholds were chosen
- Private merchant/customer data
- Internal reasoning for rules

---

## What TO Tell AI

✅ Do provide:
- What to build (SPEC.md)
- How to build it (RULES.md)
- Safety constraints (SAFETY_RULES.md)
- Current task (MASTER_TASK_CHECKLIST.md)
- Test requirements
- Integration points

---

## Review Before Merging

After AI delivers code:

1. **Check against SAFETY_RULES.md**
   - No secrets in logs? ✓
   - Idempotency implemented? ✓
   - Audit logging present? ✓
   - Policy checks enforced? ✓

2. **Check against RULES.md**
   - Deterministic (not heuristic)? ✓
   - Policy respected? ✓
   - Everything logged? ✓
   - Error handling explicit? ✓

3. **Run tests**
   - All unit tests pass? ✓
   - Integration tests pass? ✓
   - No hardcoded values? ✓
   - No N+1 queries? ✓

4. **Update MASTER_TASK_CHECKLIST.md**
   - Mark task as COMPLETE
   - Add review date
   - Note any issues found

---

## Red Flags (AI Mistakes)

Watch for these common AI mistakes:

❌ **Heuristic-based decisions**
```python
if llm.classify_error(error_code):  # AI guessing
```

❌ **Hardcoded thresholds**
```python
if attempts > 5:  # Where did 5 come from?
```

❌ **Silent errors**
```python
try:
    action()
except:
    pass  # No log
```

❌ **No idempotency**
```python
def send_sms(phone):
    provider.send(phone, msg)  # Sent twice if webhook retried
```

❌ **Policy bypass**
```python
if merchant.sms_disabled:
    send_sms_anyway()  # Override policy
```

---

## Good Signs (AI Did It Right)

✅ **Explicit policy checks**
```python
if not merchant_policy.sms_enabled:
    return
```

✅ **Comprehensive logging**
```python
audit_log.insert(event_type="SMS_SENT", details={...})
```

✅ **Idempotency keys**
```python
idempotency_key = hash(payment_id + action_type)
if db.check_existing(idempotency_key):
    return db.get_result(idempotency_key)
```

✅ **Database constraints**
```sql
CREATE TABLE action (
    idempotency_key VARCHAR UNIQUE  -- Can't duplicate
)
```

✅ **Deterministic mapping**
```python
ERROR_CODE_MAPPING = {
    ("BAD_REQUEST_ERROR", "Card has expired"): FailureType.CARD_EXPIRED,
}
```

---

## Phase-by-Phase Instructions

### Phase 2: Database Layer
Give AI: SPEC.md (Phase 2), RULES.md, migrations/001_initial_schema.sql
Task: Create SQLAlchemy ORM + CRUD functions
Review: Check no business logic in queries, all transactions are explicit

### Phase 3: Webhook Receiver
Give AI: SPEC.md (Phase 3), RULES.md, models.py
Task: Implement webhook signature verification + deduplication
Review: Check no processing without signature, duplicates are skipped

### Phase 4: Diagnosis Engine
Give AI: SPEC.md (Phase 4), RULES.md, config.py
Task: Implement error → FailureType mapping
Review: Check only uses ERROR_CODE_MAPPING table (no heuristics)

### Phase 5: Policy Engine
Give AI: SPEC.md (Phase 5), RULES.md
Task: Implement merchant + customer policy checks
Review: Check policies can't be overridden, all checks are logged

---

## Checklist Before Committing

- [ ] Code follows all 15 RULES
- [ ] Code follows SAFETY_RULES
- [ ] All critical paths have audit logs
- [ ] No secrets in logs
- [ ] Idempotency keys implemented (if applicable)
- [ ] Policy checks enforced (if applicable)
- [ ] Tests pass
- [ ] No hardcoded thresholds
- [ ] Error handling is explicit
- [ ] Deterministic (not heuristic-based)
- [ ] MASTER_TASK_CHECKLIST updated

---

## Support

If AI is confused:
1. Point to RULES.md section
2. Provide example (good + bad)
3. Paste relevant SPEC.md section
4. Give current task number

If AI produces code that violates rules:
1. Don't commit it
2. Reference the rule violated
3. Ask AI to fix it
4. Review again

---

**Rule of thumb:** If it's not in SPEC.md/RULES.md/SAFETY_RULES.md, the AI shouldn't do it.
