# INSTRUCTION.md — Step-by-Step Build Instructions

**Use this to guide implementation of each phase.**

---

## How to Use This Document

For each phase:
1. Read the phase overview
2. Follow the prerequisites checklist
3. Implement tasks in order
4. Run tests after each task
5. Update MASTER_TASK_CHECKLIST.md
6. Commit when phase complete

---

## PHASE 0-1: Foundation (COMPLETE) ✅

**Status:** Done. Foundation is ready.

No further action needed. Proceed to Phase 2.

---

## PHASE 2: Database Layer (Next Phase)

**Objective:** Create SQLAlchemy ORM models and CRUD functions for all 10 tables.

**Prerequisites:**
- [ ] Phase 0-1 complete
- [ ] Docker running locally (`docker-compose up`)
- [ ] Database tables exist (check: `docker-compose exec postgres psql -U postgres -d payment_recovery -c "\dt"`)
- [ ] Read SPEC.md (Phase 2 section)
- [ ] Read RULES.md
- [ ] Read SAFETY_RULES.md

### Files to Create

```
src/
└── database/
    ├── __init__.py
    ├── models.py              # SQLAlchemy ORM models
    └── queries.py             # CRUD functions
```

### Implementation Steps

**Step 1: Create Directory Structure**
```bash
mkdir -p src/database
touch src/database/__init__.py
```

**Step 2: Create models.py (Task 30)**

Import SQLAlchemy Base and create ORM models for each table in migrations/001_initial_schema.sql:

```python
# src/database/models.py
from sqlalchemy import Column, String, UUID, DateTime, JSON, Integer, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class PaymentFailureEvent(Base):
    __tablename__ = "payment_failure_event"
    
    failure_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    payment_id = Column(String, nullable=False)
    merchant_id = Column(String, nullable=False)
    customer_id = Column(String, nullable=False)
    failure_type = Column(String, nullable=False)  # Maps to FailureType enum
    error_code = Column(String, nullable=False)
    error_description = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # RecoveryStatus
    detected_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Add relationships to other tables later if needed

class FailureRecoveryAction(Base):
    __tablename__ = "failure_recovery_action"
    
    action_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    failure_id = Column(UUID, nullable=False)  # FK to payment_failure_event
    payment_id = Column(String, nullable=False)
    merchant_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)  # ActionType enum
    status = Column(String, nullable=False, default="PENDING")
    idempotency_key = Column(String, unique=True, nullable=False)
    config = Column(JSON, nullable=True)  # Action-specific config
    result = Column(JSON, nullable=True)  # Action result/response
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ... create remaining 8 models following same pattern
```

**Checklist for models.py:**
- [ ] All 10 tables have ORM models
- [ ] All columns map to schema exactly
- [ ] All timestamps present (created_at, updated_at)
- [ ] UUID primary keys (not integers)
- [ ] Foreign key references correct
- [ ] No business logic in models (just columns)
- [ ] All models inherit from Base

**Step 3: Create queries.py (Tasks 31-43)**

Create CRUD functions. Each function:
- Takes Pydantic input model
- Performs DB operation
- Returns Pydantic output model
- Logs to audit_log
- Handles errors explicitly

**Example structure:**

```python
# src/database/queries.py
from sqlalchemy.orm import Session
from models import PaymentFailureEvent as PaymentFailureEventModel
from models import (... all ORM models ...)
from models import (... all Pydantic models ...)

def insert_payment_failure_event(
    db: Session,
    payment_payload: PaymentPayload,
    detected_at: datetime,
) -> str:
    """
    Insert payment failure event into database.
    
    Args:
        db: Database session
        payment_payload: Payment data from Razorpay webhook
        detected_at: When failure was detected
    
    Returns:
        failure_id (UUID as string)
    
    Raises:
        DatabaseError: If insert fails
    """
    try:
        failure = PaymentFailureEventModel(
            failure_id=uuid.uuid4(),
            payment_id=payment_payload.id,
            merchant_id=extract_merchant_id(payment_payload),
            customer_id=extract_customer_id(payment_payload),
            failure_type="PENDING",  # Will be updated after diagnosis
            error_code=payment_payload.error_code,
            error_description=payment_payload.error_description,
            status="PENDING",
            detected_at=detected_at,
        )
        db.add(failure)
        db.commit()
        
        # Log to audit_log
        log_audit_event(
            db,
            event_type="FAILURE_DETECTED",
            actor="WEBHOOK_RECEIVER",
            payment_id=payment_payload.id,
            failure_id=str(failure.failure_id),
            details={
                "error_code": payment_payload.error_code,
                "error_description": payment_payload.error_description,
            },
        )
        
        return str(failure.failure_id)
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Duplicate payment failure: {e}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inserting payment failure: {e}")
        raise

def get_payment_failure_by_id(db: Session, failure_id: str) -> PaymentFailureEvent:
    """Get payment failure by ID."""
    # Implementation...

def update_failure_status(
    db: Session,
    failure_id: str,
    new_status: RecoveryStatus,
) -> None:
    """Update failure status."""
    # Implementation...

# ... implement 18 more CRUD functions following same pattern
```

**Checklist for queries.py:**
- [ ] 20 CRUD functions (one per task)
- [ ] Every function has type hints
- [ ] Every function has docstring
- [ ] Every function logs to audit_log (if applicable)
- [ ] Every function handles errors
- [ ] No N+1 queries
- [ ] Transactions used for multi-table updates
- [ ] Idempotency checks where needed

**Step 4: Database Connection Setup**

Create connection factory in config.py or separate database.py:

```python
# In src/database/__init__.py or config.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 5: Tests (in tests/test_database.py)**

Write tests for each CRUD function:

```python
# tests/test_database.py

def test_insert_payment_failure_event():
    """Test inserting payment failure."""
    db = TestDatabase()
    
    failure_id = insert_payment_failure_event(
        db,
        payment_payload=PaymentPayload(...),
        detected_at=datetime.utcnow(),
    )
    
    assert failure_id is not None
    
    failure = get_payment_failure_by_id(db, failure_id)
    assert failure.payment_id == "pay_123456"
    assert failure.status == "PENDING"
    
    # Verify audit log was created
    audit_entries = db.query(AuditLog).filter_by(failure_id=failure_id).all()
    assert len(audit_entries) > 0

# ... write tests for all CRUD functions
```

### Success Criteria

After Phase 2:
- [ ] All 10 ORM models created and working
- [ ] All 20 CRUD functions implemented
- [ ] All functions have type hints + docstrings
- [ ] All functions log to audit_log
- [ ] Database connection pooling configured
- [ ] All tests passing (80%+ coverage)
- [ ] No N+1 queries
- [ ] Transactions working correctly
- [ ] MASTER_TASK_CHECKLIST.md updated (23 ✅ + 20 ✅ = 43)

### Effort Estimate
- **Time:** 3-4 days full-time
- **Lines of Code:** 1000-1500
- **Tests:** 20+ unit tests + integration tests

### When Phase 2 is Complete

1. All tasks marked [x] in MASTER_TASK_CHECKLIST.md
2. All tests pass: `pytest`
3. Code review: All rules followed
4. Commit: `git commit -m "Phase 2: Database Layer (20 tasks complete)"`
5. Proceed to Phase 3

---

## PHASE 3: Webhook Receiver

**Objective:** Implement webhook signature verification, parsing, deduplication, and queuing.

**Prerequisites:**
- [ ] Phase 2 complete
- [ ] Read SPEC.md (Phase 3)
- [ ] Models from Phase 0-1
- [ ] Database layer from Phase 2

### Implementation Overview

1. **Webhook Endpoint** (main.py, already stubbed)
2. **Signature Verification** — HMAC-SHA256 check
3. **Payload Parsing** — JSON → RazorpayWebhook model
4. **Deduplication** — Check idempotency key
5. **Database Insert** — Create failure record
6. **Queue** — Push to Redis for async processing
7. **Response** — Return acknowledgment

### Key Tasks (8 tasks)
- Task 44: Signature verification
- Task 45: Payload parsing
- Task 46: Deduplication
- Task 47: Extract payment data
- Task 48: Create failure record
- Task 49: Queue for async
- Task 50: Error handling
- Task 51: Response format

### When to Proceed

After Phase 2 complete, proceed to Phase 3.

---

## PHASE 4+: Continue Following Pattern

For each phase:
1. Read phase specification in SPEC.md
2. Check prerequisites
3. Create necessary files
4. Implement tasks in order
5. Write tests
6. Update checklist
7. Commit when complete
8. Proceed to next phase

---

## Development Workflow

### Daily Workflow

```bash
# Start day
docker-compose up

# Check status
grep -A 5 "Phase X Summary" MASTER_TASK_CHECKLIST.md

# Pick next task
# Implement → Test → Commit → Update Checklist

# Commit pattern:
git commit -m "Phase X, Task Y: [description]
- Implemented: [what was done]
- Tests: [tests added]
- Verified: [verification steps]"

# End day
docker-compose down
```

### When Stuck

1. Check SPEC.md section for phase
2. Check RULES.md for constraints
3. Check existing Phase 0-1 code for patterns
4. Run tests to see what's failing
5. Check database schema to understand data model
6. Ask for clarification (better than guessing)

### Testing Pattern

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_database.py::test_insert_payment_failure_event

# Run with coverage
pytest --cov=src tests/

# Must have 80%+ coverage to proceed
```

---

## Deployment Milestones

After each phase:

- [ ] All tasks complete
- [ ] All tests passing (80%+)
- [ ] Code review passed
- [ ] No new TODOs
- [ ] Documentation updated
- [ ] MASTER_TASK_CHECKLIST.md updated
- [ ] Committed to git

---

## Quick Reference

**Start Phase 2 now:**
1. Read SPEC.md (Phase 2)
2. Create src/database/ directory
3. Create models.py (10 ORM models)
4. Create queries.py (20 CRUD functions)
5. Write tests
6. Run: `pytest`
7. Update checklist
8. Commit

**Time to Phase 2 completion:** 3-4 days

---

**Questions? Check SPEC.md, RULES.md, or look at Phase 0-1 code for patterns.**

