# AI_GUIDELINES.md — Decision-Making for AI-Based Development

**Use this when AI is making architectural or code decisions.**

---

## Core Principle: Deterministic > Intelligent

When AI must choose between:
- **Deterministic (lookup table, config, rules)** → Always choose this
- **Intelligent (heuristic, ML, AI-based)** → Never choose this

**Example:**
- Error classification: Deterministic lookup table (not ML)
- Customer risk: Rule-based on account age + history (not LLM scoring)
- Action selection: Scoring based on historical success rates (not AI ranking)

---

## Constraint-Driven Development

AI must follow these constraints IN ORDER OF PRIORITY:

1. **Safety** (from SAFETY_RULES.md)
2. **Correctness** (from SPEC.md)
3. **Performance** (optimization is secondary)
4. **Elegance** (code style is last)

If performance conflicts with safety, choose safety.  
If elegance conflicts with correctness, choose correctness.

---

## Decision Framework

When AI is unsure what to do:

### Question 1: Is this in SPEC.md?
- **YES** → Follow SPEC.md exactly
- **NO** → Don't add new functionality (out of scope)

### Question 2: Is this in RULES.md or SAFETY_RULES.md?
- **YES** → Follow the rule exactly (no exceptions without approval)
- **NO** → Use best judgment

### Question 3: Can this fail?
- **YES** → Add error handling + logging (RULES.md #13)
- **NO** → Proceed

### Question 4: Is this auditable?
- **YES** → Proceed
- **NO** → Add audit log entry (RULES.md #3)

---

## Common AI Mistakes to Avoid

### Mistake 1: Being Too Clever

❌ **AI tries to be clever:**
```python
# One-liner with complex logic
return [a for a in actions if score(a) > threshold and policy.allows(a)]
```

✅ **Explicit step-by-step:**
```python
eligible_actions = []
for action in actions:
    if not policy.allows(action):
        continue
    score = calculate_score(action)
    if score > threshold:
        eligible_actions.append(action)
return eligible_actions
```

### Mistake 2: Anticipating Future Needs

❌ **AI over-engineers:**
```python
# "In the future, we might need multi-cloud support"
def get_database(cloud_provider="aws"):
    if cloud_provider == "aws":
        return AWSDatabase()
    elif cloud_provider == "gcp":
        return GCPDatabase()
```

✅ **Build exactly what's needed:**
```python
# PostgreSQL via docker-compose locally, managed service in prod
def get_database():
    return SQLAlchemy(DATABASE_URL)
```

### Mistake 3: Rewriting Existing Code

❌ **AI rewrites what already exists:**
```python
# models.py already has DiagnosisResult
# But AI creates its own:
class DiagnosisOutput(BaseModel):
    failure_type: FailureType
    ...
```

✅ **Always use existing code:**
```python
from models import DiagnosisResult
# Use it as-is
```

### Mistake 4: Skipping Obvious Tests

❌ **AI implements without testing:**
```python
def classify_error(code, description):
    # No tests for this function
    return ERROR_CODE_MAPPING.get((code, description))
```

✅ **Tests are mandatory:**
```python
def test_classify_card_expired():
    assert classify_error("BAD_REQUEST_ERROR", "Card has expired") == FailureType.CARD_EXPIRED

def test_classify_unknown():
    assert classify_error("UNKNOWN", "Unknown error") == FailureType.UNKNOWN
```

### Mistake 5: Config is Code

❌ **AI hardcodes config:**
```python
MAX_RETRIES = 5
MAX_SMS_PER_CUSTOMER = 3
```

✅ **Config in config.py:**
```python
# In config.py:
MAX_RETRIES = os.getenv("MAX_RETRIES", 5)

# In .env:
MAX_RETRIES=5
```

---

## Type Safety

**Rule:** All functions must have type hints.

❌ **NO:**
```python
def classify_error(code, description):
    ...
```

✅ **YES:**
```python
def classify_error(code: str, description: str) -> FailureType:
    ...
```

This helps catch errors early.

---

## Documentation Standards

**Every function needs:**
1. Docstring explaining what it does
2. Args and return types
3. Exceptions it might raise
4. Example usage (if complex)

❌ **NO:**
```python
def calculate_score(action):
    return historical_data[action]["success_rate"]
```

✅ **YES:**
```python
def calculate_score(action: ActionType) -> float:
    """
    Calculate success probability for an action.
    
    Uses historical success rate from audit logs.
    If no history, returns 0.5 (neutral).
    
    Args:
        action: The action type to score
    
    Returns:
        float: Success probability (0-1)
    
    Raises:
        ActionTypeNotFound: If action type is unknown
    
    Example:
        >>> calculate_score(ActionType.AUTO_RETRY)
        0.95
    """
    history = load_action_history(action)
    if not history:
        return 0.5
    return history["success_rate"]
```

---

## Import Organization

```python
# Standard library (first)
import logging
from datetime import datetime
from typing import List, Dict

# Third-party (second)
from fastapi import FastAPI
from sqlalchemy import Column, String

# Local (third)
from config import settings
from models import PaymentFailureEvent
```

---

## Naming Conventions

- **Variables:** `snake_case`
- **Functions:** `snake_case_with_verb()` (do_something)
- **Classes:** `PascalCase`
- **Constants:** `UPPER_CASE`
- **Database tables:** `snake_case` (plural-ish)

✅ **GOOD:**
```python
def calculate_recovery_score(action_type: ActionType) -> float:
    MAX_SCORE = 1.0
    
    class ScoreCalculator:
        def __init__(self, action_type):
            self.action_type = action_type
```

---

## Error Messages

**Make errors helpful:**

❌ **Unhelpful:**
```python
raise ValueError("Invalid value")
```

✅ **Helpful:**
```python
raise ValueError(
    f"max_retries must be >= 1, got {max_retries}. "
    f"Check MerchantPolicy configuration for merchant {merchant_id}"
)
```

---

## Logging Standards

❌ **Too vague:**
```python
logger.info("Processing failure")
```

✅ **Informative:**
```python
logger.info(
    f"Processing payment failure",
    extra={
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "failure_type": failure_type.value,
        "timestamp": datetime.utcnow().isoformat(),
    }
)
```

---

## When to Ask for Help

AI should ask human for help when:

1. **Unsure about scope** — "Is this in scope for Phase X?"
2. **Conflict with rules** — "Rule #5 says X but task requires Y"
3. **Performance vs safety** — "This would be faster but less auditable"
4. **Design decision** — "Should we cache this or query fresh?"
5. **Ambiguous spec** — "SPEC.md says A and B but they conflict"

Good question:
```
I'm implementing Phase 3, Task 44 (Webhook Signature Verification).
The spec says to use HMAC-SHA256.
Razorpay docs mention SHA256 or RSA.

Should I support both or only SHA256?
Which is in current use?
```

---

## Testing Mindset

Before implementing:
- What's the happy path?
- What could fail?
- How should errors be handled?
- Is this testable?

---

## Code Review Checklist

AI-generated code should pass:

- [ ] Follows all 15 RULES
- [ ] Follows all SAFETY_RULES
- [ ] Has type hints
- [ ] Has docstrings
- [ ] Error handling is explicit
- [ ] No hardcoded config
- [ ] Uses existing models
- [ ] Tests pass
- [ ] No N+1 queries
- [ ] Audit logged (if applicable)
- [ ] No secrets in logs

---

## When Stuck

If AI doesn't know what to do:

1. **Check SPEC.md** (what to build)
2. **Check RULES.md** (how to build)
3. **Check existing code** (pattern to follow)
4. **Check migrations** (schema context)
5. **Ask for clarification** (don't guess)

---

**The best AI code is code that follows the rules perfectly.**

