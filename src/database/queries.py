"""CRUD functions for the payment recovery database (Phase 2, Tasks 31-43).

Rules enforced here:
- All operations are transactional and roll back on error.
- Mutations write audit_log entries in the same transaction.
- Idempotency is checked before inserts of retry-able operations.
- No business logic: pure data access with explicit error handling.
- No secrets are ever logged (error type names only).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from config import (
    AUDIT_LOG_ACTORS, AUDIT_LOG_EVENTS, IDEMPOTENCY_EXPIRY_SECONDS,
)
from models import ActionType, PaymentPayload, RecoveryStatus
from src.database.models import (
    AuditLog, CustomerRecord, DiagnosisCache, FailureRecoveryAction,
    IdempotencyKey, MerchantPolicy, OutcomeRecord, PaymentFailureEvent,
    SMSDeliveryTracking, SupportEscalation,
)

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class DuplicateRecordError(DatabaseError):
    """Raised when a uniqueness constraint is violated."""


@contextmanager
def transaction(db: Session) -> Iterator[Session]:
    """Wrap a session in an explicit transaction.

    Commits on success; rolls back and re-raises on any failure so
    related changes are atomic (all succeed or all fail).

    Args:
        db: Database session.

    Yields:
        The same session within begin/commit/rollback scope.

    Raises:
        DatabaseError: Wrapped SQLAlchemy failure after rollback.
    """
    try:
        yield db
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "Transaction rolled back: %s", type(exc).__name__
        )
        raise DatabaseError(type(exc).__name__) from exc
    except Exception:
        db.rollback()
        raise


def _flush_with_unique_handling(db: Session, entity: Any) -> None:
    """Flush an insert, converting uniqueness violations to typed errors."""
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        duplicate = (
            getattr(exc.orig, "pgcode", None) == "23505"
            or getattr(exc.orig, "sqlstate", None) == "23505"
            or getattr(exc.orig, "sqlite_errorname", None)
            in {"SQLITE_CONSTRAINT_UNIQUE", "SQLITE_CONSTRAINT_PRIMARYKEY"}
        )
        logger.warning("Insert rejected: %s", type(exc).__name__)
        if duplicate:
            raise DuplicateRecordError(type(entity).__name__) from None
        raise DatabaseError("Integrity constraint violation") from None
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database operation failed: %s", type(exc).__name__)
        raise DatabaseError("Database operation failed") from None


def log_audit_event(
    db: Session,
    payment_id: str,
    merchant_id: str,
    event_type: str,
    actor: str,
    details: dict[str, Any],
    failure_id: UUID | str | None = None,
    action_id: UUID | str | None = None,
) -> UUID:
    """Insert an audit_log entry with full decision context.

    Args:
        db: Database session.
        payment_id: Razorpay payment ID.
        merchant_id: Merchant identifier.
        event_type: One of AUDIT_LOG_EVENTS keys.
        actor: One of AUDIT_LOG_ACTORS keys.
        details: Full decision context (must contain no secrets).
        failure_id: Optional related failure.
        action_id: Optional related action.

    Returns:
        audit_id of the created entry.

    Raises:
        DatabaseError: If the insert fails.
    """
    if event_type not in AUDIT_LOG_EVENTS:
        raise ValueError(
            "event_type must be a configured AUDIT_LOG_EVENTS key"
        )
    if actor not in AUDIT_LOG_ACTORS:
        raise ValueError("actor must be a configured AUDIT_LOG_ACTORS key")
    entry = AuditLog(
        payment_id=payment_id,
        merchant_id=merchant_id,
        event_type=event_type,
        actor=actor,
        details=details,
        failure_id=UUID(str(failure_id)) if failure_id else None,
        action_id=UUID(str(action_id)) if action_id else None,
    )
    try:
        db.add(entry)
        _flush_with_unique_handling(db, entry)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Audit insert failed: %s", type(exc).__name__)
        raise DatabaseError("Audit insert failed") from None
    except Exception:
        db.rollback()
        raise
    return entry.audit_id


def check_idempotency(
    db: Session, idempotency_key: str
) -> dict[str, Any] | None:
    """Return the stored result for a key, or None if unseen or expired.

    Args:
        db: Database session.
        idempotency_key: Deterministic operation key.

    Returns:
        The recorded result of the first execution, else None.
    """
    try:
        entry = db.scalar(
            select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Idempotency lookup failed: %s", type(exc).__name__)
        raise DatabaseError("Idempotency lookup failed") from None
    if entry is None:
        return None
    if entry.expires_at <= datetime.utcnow():
        return None
    return dict(entry.result)


def record_idempotency_key(
    db: Session,
    idempotency_key: str,
    payment_id: str,
    operation_type: str,
    result: dict[str, Any],
) -> None:
    """Record an idempotent operation result within the caller's transaction.

    Args:
        db: Database session.
        idempotency_key: Deterministic operation key.
        payment_id: Related payment.
        operation_type: Operation category (e.g., ACTION_EXECUTED).
        result: Result payload of the first execution.

    Raises:
        DuplicateRecordError: If the key already exists.
        DatabaseError: If the insert fails.
    """
    now = datetime.utcnow()
    entry = IdempotencyKey(
        key=idempotency_key,
        payment_id=payment_id,
        operation_type=operation_type,
        result=result,
        created_at=now,
        expires_at=now + timedelta(seconds=IDEMPOTENCY_EXPIRY_SECONDS),
    )
    try:
        db.add(entry)
        _flush_with_unique_handling(db, entry)
    except Exception:
        db.rollback()
        raise


def insert_payment_failure_event(
    db: Session,
    payment_payload: PaymentPayload,
    detected_at: datetime,
    *,
    merchant_id: str,
    customer_id: str,
    webhook_event_id: str,
) -> UUID:
    """Insert a payment_failure_event row and audit FAILURE_DETECTED.

    Args:
        db: Database session.
        payment_payload: Validated Razorpay payment data.
        merchant_id: Explicit merchant identifier, not inferred from notes.
        customer_id: Explicit customer identifier, not inferred from contact.
        webhook_event_id: Razorpay event ID (deduplication key).
        detected_at: Failure detection time.

    Returns:
        failure_id of the created event.

    Raises:
        DuplicateRecordError: If payment_id or webhook_event_id is duplicate.
        DatabaseError: If the insert fails.
    """
    failure = PaymentFailureEvent(
        payment_id=payment_payload.id,
        order_id=payment_payload.order_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        amount=payment_payload.amount,
        currency=payment_payload.currency,
        error_code=payment_payload.error_code,
        error_description=payment_payload.error_description,
        payment_method=payment_payload.method.value,
        webhook_event_id=webhook_event_id,
        detected_at=detected_at,
    )
    try:
        db.add(failure)
        _flush_with_unique_handling(db, failure)
        log_audit_event(
            db,
            payment_id=payment_payload.id,
            merchant_id=merchant_id,
            event_type="FAILURE_DETECTED",
            actor="DETECTION_ENGINE",
            details={
                "error_code": payment_payload.error_code,
                "webhook_event_id": webhook_event_id,
            },
            failure_id=failure.failure_id,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Failure insertion failed: %s", type(exc).__name__)
        raise DatabaseError("Failure insertion failed") from None
    except Exception:
        db.rollback()
        raise
    return failure.failure_id


def get_payment_failure_by_id(
    db: Session, failure_id: UUID | str
) -> PaymentFailureEvent | None:
    """Fetch a payment failure event by ID.

    Args:
        db: Database session.
        failure_id: UUID of the failure.

    Returns:
        The event or None if not found.
    """
    identifier = UUID(str(failure_id))
    try:
        return db.scalar(
            select(PaymentFailureEvent).where(
                PaymentFailureEvent.failure_id == identifier
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Failure lookup failed: %s", type(exc).__name__)
        raise DatabaseError("Failure lookup failed") from None


def update_failure_status(
    db: Session,
    failure_id: UUID | str,
    new_status: RecoveryStatus | str,
    actor: str,
    reason: str,
    *,
    idempotency_key: str,
) -> None:
    """Update failure status and audit the transition in one transaction.

    Args:
        db: Database session.
        failure_id: UUID of the failure.
        new_status: Target RecoveryStatus value.
        actor: Component performing the update.
        reason: Why the status changed.

    Raises:
        ValueError: If the failure does not exist.
        DatabaseError: If the update fails.
    """
    identifier = UUID(str(failure_id))
    status = RecoveryStatus(new_status).value
    if not idempotency_key or len(idempotency_key) > 255:
        raise ValueError("Idempotency key must contain 1 to 255 characters")
    result = {"failure_id": str(identifier), "status": status,
              "actor": actor, "reason": reason}
    try:
        failure = db.scalar(
            select(PaymentFailureEvent)
            .where(PaymentFailureEvent.failure_id == identifier)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if failure is None:
            raise ValueError("Failure not found")
        existing = db.get(IdempotencyKey, idempotency_key)
        if existing is not None:
            if (existing.operation_type != "UPDATE_FAILURE_STATUS"
                    or existing.payment_id != failure.payment_id
                    or existing.result != result):
                raise ValueError("Idempotency key conflicts with operation")
            return
        record_idempotency_key(
            db, idempotency_key, failure.payment_id,
            "UPDATE_FAILURE_STATUS", result,
        )
        old_status = failure.status
        failure.status = status
        event_type = {
            "PENDING": "FAILURE_DETECTED",
            "DIAGNOSED": "DIAGNOSIS_COMPLETE",
            "CLOSED": "OUTCOME_RECORDED",
        }.get(status, status)
        log_audit_event(
            db,
            payment_id=failure.payment_id,
            merchant_id=failure.merchant_id,
            event_type=event_type,
            actor=actor,
            details={"from": old_status, "to": status, "reason": reason,
                     "operation": "UPDATE_FAILURE_STATUS",
                     "idempotency_key": idempotency_key},
            failure_id=failure.failure_id,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Status update failed: %s", type(exc).__name__)
        raise DatabaseError("Status update failed") from None
    except Exception:
        db.rollback()
        raise


def insert_recovery_action(
    db: Session,
    failure_id: UUID | str,
    payment_id: str,
    merchant_id: str,
    customer_id: str,
    action_type: str,
    idempotency_key: str,
    config: dict[str, Any],
    scheduled_at: datetime | None = None,
) -> UUID:
    """Create a recovery action after an idempotency check.

    The database UNIQUE constraint is trusted to prevent double inserts
    under concurrency; the pre-check is a fast-path only.

    Args:
        db: Database session.
        failure_id: Parent failure UUID.
        payment_id: Razorpay payment ID.
        merchant_id: Merchant identifier.
        customer_id: Customer identifier.
        action_type: One of ActionType values.
        idempotency_key: Deterministic action key.
        config: Action-specific configuration.
        scheduled_at: Optional scheduled execution time.

    Returns:
        action_id of the created action.

    Raises:
        DuplicateRecordError: If the idempotency key already exists.
        DatabaseError: If the insert fails.
    """
    if not idempotency_key or len(idempotency_key) > 255:
        raise ValueError("Idempotency key must contain 1 to 255 characters")
    action_type = ActionType(action_type).value
    try:
        failure = get_payment_failure_by_id(db, failure_id)
        if failure is None:
            raise ValueError("Failure not found")
        if (failure.payment_id, failure.merchant_id, failure.customer_id) != (
            payment_id, merchant_id, customer_id
        ):
            raise ValueError("Action identifiers do not match failure")
        existing = check_idempotency(db, idempotency_key)
        if existing is not None:
            raise DuplicateRecordError("IdempotencyKey")
        action = FailureRecoveryAction(
            failure_id=failure.failure_id,
            payment_id=payment_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            action_type=action_type,
            idempotency_key=idempotency_key,
            config=config,
            scheduled_at=scheduled_at,
        )
        db.add(action)
        _flush_with_unique_handling(db, action)
        log_audit_event(
            db,
            payment_id=payment_id,
            merchant_id=merchant_id,
            event_type="STRATEGY_SELECTED",
            actor="ACTION_EXECUTOR",
            details={"action_type": action_type,
                     "idempotency_key": idempotency_key,
                     "operation": "ACTION_CREATED", "status": "PENDING"},
            failure_id=failure.failure_id,
            action_id=action.action_id,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Action insertion failed: %s", type(exc).__name__)
        raise DatabaseError("Action insertion failed") from None
    except Exception:
        db.rollback()
        raise
    return action.action_id


def get_recovery_actions_for_failure(
    db: Session, failure_id: UUID | str
) -> list[FailureRecoveryAction]:
    """List all recovery actions for one failure (single query).

    Args:
        db: Database session.
        failure_id: UUID of the failure.

    Returns:
        Actions ordered by creation time.
    """
    try:
        return list(
            db.scalars(
                select(FailureRecoveryAction)
                .where(
                    FailureRecoveryAction.failure_id == UUID(str(failure_id))
                )
                .order_by(FailureRecoveryAction.created_at)
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Action lookup failed: %s", type(exc).__name__)
        raise DatabaseError("Action lookup failed") from None


def get_merchant_policy(
    db: Session, merchant_id: str
) -> MerchantPolicy | None:
    """Fetch a merchant policy by merchant ID.

    Args:
        db: Database session.
        merchant_id: Merchant identifier.

    Returns:
        The policy or None if not configured.
    """
    try:
        return db.scalar(
            select(MerchantPolicy).where(
                MerchantPolicy.merchant_id == merchant_id
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Merchant policy lookup failed: %s", type(exc).__name__)
        raise DatabaseError("Merchant policy lookup failed") from None


def update_merchant_policy(
    db: Session,
    merchant_id: str,
    updates: dict[str, Any],
    actor: str,
    *,
    idempotency_key: str,
) -> MerchantPolicy:
    """Update a merchant policy and audit the change.

    Args:
        db: Database session.
        merchant_id: Merchant identifier.
        updates: Column values to set.
        actor: Component or admin performing the update.

    Returns:
        The updated policy.

    Raises:
        ValueError: If the policy does not exist.
        DatabaseError: If the update fails.
    """
    if not idempotency_key or len(idempotency_key) > 255:
        raise ValueError("Idempotency key must contain 1 to 255 characters")
    columns = set(MerchantPolicy.__table__.columns.keys()) - {
        "policy_id", "merchant_id", "created_at", "updated_at",
    }
    if not set(updates) <= columns:
        raise ValueError("Unknown policy column or immutable field")
    result = {"merchant_id": merchant_id, "updates": updates, "actor": actor}
    try:
        policy = db.scalar(
            select(MerchantPolicy)
            .where(MerchantPolicy.merchant_id == merchant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if policy is None:
            raise ValueError("Merchant policy not found")
        existing = db.get(IdempotencyKey, idempotency_key)
        if existing is not None:
            if (existing.operation_type != "UPDATE_MERCHANT_POLICY"
                    or existing.result != result):
                raise ValueError("Idempotency key conflicts with operation")
            return policy
        record_idempotency_key(
            db, idempotency_key, "N/A", "UPDATE_MERCHANT_POLICY", result,
        )
        before = {column: getattr(policy, column) for column in updates}
        for column, value in updates.items():
            setattr(policy, column, value)
        log_audit_event(
            db, payment_id="N/A", merchant_id=merchant_id,
            event_type="OUTCOME_RECORDED", actor=actor,
            details={"operation": "UPDATE_MERCHANT_POLICY",
                     "idempotency_key": idempotency_key,
                     "policy_update": {"before": before, "after": updates}},
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Policy update failed: %s", type(exc).__name__)
        raise DatabaseError("Policy update failed") from None
    except Exception:
        db.rollback()
        raise
    return policy


def get_customer_record(
    db: Session, customer_id: str
) -> CustomerRecord | None:
    """Fetch customer history and risk data.

    Args:
        db: Database session.
        customer_id: Customer identifier.

    Returns:
        The record or None if the customer is new.
    """
    try:
        return db.scalar(
            select(CustomerRecord).where(
                CustomerRecord.customer_id == customer_id
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Customer lookup failed: %s", type(exc).__name__)
        raise DatabaseError("Customer lookup failed") from None


def record_sms_delivery(
    db: Session,
    action_id: UUID | str,
    payment_id: str,
    customer_id: str,
    merchant_id: str,
    phone_number: str,
    message_text: str,
    provider: str,
    provider_message_id: str | None = None,
    status: str = "SENT",
) -> UUID:
    """Insert an SMS delivery tracking record.

    Args:
        db: Database session.
        action_id: Parent recovery action UUID.
        payment_id: Razorpay payment ID.
        customer_id: Customer identifier.
        merchant_id: Merchant identifier.
        phone_number: Customer phone (never logged).
        message_text: Message body (never logged).
        provider: SMS provider name.
        provider_message_id: Provider message reference.
        status: Initial delivery status.

    Returns:
        sms_id of the created record.

    Raises:
        DatabaseError: If the insert fails.
    """
    try:
        action = db.get(FailureRecoveryAction, UUID(str(action_id)))
        if action is None:
            raise ValueError("Recovery action not found")
        if (action.payment_id, action.customer_id, action.merchant_id) != (
            payment_id, customer_id, merchant_id
        ):
            raise ValueError("SMS identifiers do not match recovery action")
        record = SMSDeliveryTracking(
            action_id=action.action_id,
            payment_id=payment_id,
            customer_id=customer_id,
            merchant_id=merchant_id,
            phone_number=phone_number,
            message_text=message_text,
            provider=provider,
            provider_message_id=provider_message_id,
            status=status,
        )
        db.add(record)
        _flush_with_unique_handling(db, record)
        log_audit_event(
            db, payment_id, merchant_id, "OUTCOME_RECORDED",
            "OUTCOME_TRACKER",
            {"operation": "SMS_DELIVERY_RECORDED",
             "sms_id": str(record.sms_id), "status": status},
            failure_id=action.failure_id, action_id=action.action_id,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("SMS recording failed: %s", type(exc).__name__)
        raise DatabaseError("SMS recording failed") from None
    except Exception:
        db.rollback()
        raise
    return record.sms_id


def record_outcome(
    db: Session,
    payment_id: str,
    failure_id: UUID | str,
    outcome_type: str,
    success: bool,
    details: dict[str, Any],
    action_id: UUID | str | None = None,
    *,
    idempotency_key: str,
    new_status: RecoveryStatus | str | None = None,
) -> UUID:
    """Insert an outcome and optionally apply a caller-supplied status.

    Outcome, explicit status, audit and idempotency key share a transaction.

    Args:
        db: Database session.
        payment_id: Razorpay payment ID.
        failure_id: Parent failure UUID.
        outcome_type: One of outcome_record outcome types.
        success: Whether the recovery succeeded.
        details: Full outcome context (no secrets).
        action_id: Optional originating action.

    Returns:
        outcome_id of the created record.

    Raises:
        ValueError: If the failure does not exist.
        DatabaseError: If the insert fails.
    """
    identifier = UUID(str(failure_id))
    action_identifier = UUID(str(action_id)) if action_id else None
    status = (
        RecoveryStatus(new_status).value if new_status is not None else None
    )
    if not idempotency_key or len(idempotency_key) > 255:
        raise ValueError("Idempotency key must contain 1 to 255 characters")
    request = {
        "failure_id": str(identifier), "payment_id": payment_id,
        "action_id": str(action_identifier) if action_identifier else None,
        "outcome_type": outcome_type, "success": success,
        "details": details, "new_status": status,
    }
    try:
        failure = db.scalar(
            select(PaymentFailureEvent)
            .where(PaymentFailureEvent.failure_id == identifier)
            .with_for_update().execution_options(populate_existing=True)
        )
        if failure is None:
            raise ValueError("Failure not found")
        if failure.payment_id != payment_id:
            raise ValueError("Payment does not match failure")
        if action_identifier is not None:
            action = db.get(FailureRecoveryAction, action_identifier)
            if action is None or action.failure_id != identifier:
                raise ValueError("Action does not match failure")
        existing = db.get(IdempotencyKey, idempotency_key)
        if existing is not None:
            if (existing.operation_type != "RECORD_OUTCOME"
                    or existing.result.get("request") != request):
                raise ValueError("Idempotency key conflicts with operation")
            return UUID(existing.result["outcome_id"])
        outcome = OutcomeRecord(
            payment_id=payment_id, failure_id=identifier,
            action_id=action_identifier, merchant_id=failure.merchant_id,
            outcome_type=outcome_type, success=success, details=details,
        )
        db.add(outcome)
        _flush_with_unique_handling(db, outcome)
        record_idempotency_key(
            db, idempotency_key, payment_id, "RECORD_OUTCOME",
            {"request": request, "outcome_id": str(outcome.outcome_id)},
        )
        old_status = failure.status
        if status is not None:
            failure.status = status
        log_audit_event(
            db, payment_id, failure.merchant_id, "OUTCOME_RECORDED",
            "OUTCOME_TRACKER",
            {"outcome_id": str(outcome.outcome_id),
             "outcome_type": outcome_type, "success": success,
             "from": old_status, "to": failure.status},
            failure_id=identifier, action_id=action_identifier,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Outcome recording failed: %s", type(exc).__name__)
        raise DatabaseError("Outcome recording failed") from None
    except Exception:
        db.rollback()
        raise
    return outcome.outcome_id


def get_diagnosis_cache(
    db: Session, error_code_description_hash: str
) -> DiagnosisCache | None:
    """Return a cached diagnosis if present and unexpired.

    Args:
        db: Database session.
        error_code_description_hash: Hash of error code + description.

    Returns:
        Cached diagnosis or None.
    """
    entry = db.scalar(
        select(DiagnosisCache).where(
            DiagnosisCache.error_code_description_hash
            == error_code_description_hash
        )
    )
    if entry is None:
        return None
    if entry.expires_at <= datetime.utcnow():
        return None
    return entry


def insert_diagnosis_cache(
    db: Session,
    error_code_description_hash: str,
    failure_type: str,
    confidence: float,
    recoverable: bool,
    reasoning: str,
    ttl_seconds: int,
) -> UUID:
    """Cache a diagnosis result keyed by error hash.

    Args:
        db: Database session.
        error_code_description_hash: Hash of error code + description.
        failure_type: Classified FailureType value.
        confidence: Deterministic confidence 0-1.
        recoverable: Whether the type is recoverable.
        reasoning: Deterministic explanation.
        ttl_seconds: Cache lifetime.

    Returns:
        cache_id of the existing (refreshed) or newly created entry.

    Raises:
        DatabaseError: If the upsert fails.
    """
    now = datetime.utcnow()
    entry = db.scalar(
        select(DiagnosisCache).where(
            DiagnosisCache.error_code_description_hash
            == error_code_description_hash
        )
    )
    if entry is None:
        entry = DiagnosisCache(
            error_code_description_hash=error_code_description_hash,
        )
        db.add(entry)
    entry.failure_type = failure_type
    entry.confidence = confidence
    entry.recoverable = recoverable
    entry.reasoning = reasoning
    entry.created_at = now
    entry.expires_at = now + timedelta(seconds=ttl_seconds)
    _flush_with_unique_handling(db, entry)
    return entry.cache_id


def create_support_escalation(
    db: Session,
    failure_id: UUID | str,
    action_id: UUID | str,
    payment_id: str,
    merchant_id: str,
    customer_id: str,
    reason: str,
) -> UUID:
    """Create a manual escalation ticket.

    Args:
        db: Database session.
        failure_id: Parent failure UUID.
        action_id: Originating action UUID.
        payment_id: Razorpay payment ID.
        merchant_id: Merchant identifier.
        customer_id: Customer identifier.
        reason: Why manual review is needed.

    Returns:
        escalation_id of the created ticket.

    Raises:
        DatabaseError: If the insert fails.
    """
    escalation = SupportEscalation(
        failure_id=UUID(str(failure_id)),
        action_id=UUID(str(action_id)),
        payment_id=payment_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        reason=reason,
    )
    db.add(escalation)
    _flush_with_unique_handling(db, escalation)
    log_audit_event(
        db,
        payment_id=payment_id,
        merchant_id=merchant_id,
        event_type="ESCALATED",
        actor="ACTION_EXECUTOR",
        details={"reason": reason},
        failure_id=str(failure_id),
        action_id=str(action_id),
    )
    return escalation.escalation_id


def ensure_merchant_policy(
    db: Session,
    merchant_id: str,
    defaults: dict[str, Any],
) -> MerchantPolicy:
    """Return the merchant policy, creating it from defaults if missing.

    Args:
        db: Database session.
        merchant_id: Merchant identifier.
        defaults: Column values for first-time creation.

    Returns:
        The existing or newly created policy.

    Raises:
        DatabaseError: If the insert fails.
    """
    policy = get_merchant_policy(db, merchant_id)
    if policy is not None:
        return policy
    policy = MerchantPolicy(merchant_id=merchant_id, **defaults)
    db.add(policy)
    _flush_with_unique_handling(db, policy)
    return policy


def ensure_customer_record(
    db: Session,
    customer_id: str,
    merchant_id: str,
) -> CustomerRecord:
    """Return the customer record, creating a blank one if missing.

    Args:
        db: Database session.
        customer_id: Customer identifier.
        merchant_id: Merchant identifier.

    Returns:
        The existing or newly created record.

    Raises:
        DatabaseError: If the insert fails.
    """
    record = get_customer_record(db, customer_id)
    if record is not None:
        return record
    record = CustomerRecord(
        customer_id=customer_id, merchant_id=merchant_id
    )
    db.add(record)
    _flush_with_unique_handling(db, record)
    return record


_engine = None
_session_factory: sessionmaker[Session] | None = None


def init_engine(database_url: str) -> Any:
    """Initialize a module-level engine and session factory.

    Kept for callers that configure the engine through this module
    instead of src.database.connection.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        The created engine.
    """
    global _engine, _session_factory
    from src.database.connection import create_database_engine

    _engine = create_database_engine(database_url)
    _session_factory = sessionmaker(
        bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the module session factory after init_engine."""
    if _session_factory is None:
        raise RuntimeError("Engine not initialized; call init_engine first")
    return _session_factory


def get_db() -> Iterator[Session]:
    """Yield a session from the module factory, closing it afterwards."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
