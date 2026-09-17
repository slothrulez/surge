from datetime import datetime
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, Uuid, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PaymentFailureEvent(Base):
    __tablename__ = "payment_failure_event"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'DIAGNOSED', 'POLICY_CHECK_PASSED', "
            "'POLICY_CHECK_FAILED', 'STRATEGY_SELECTED', 'ACTION_EXECUTING', "
            "'ACTION_SUCCESS', 'ACTION_FAILED', 'ESCALATED', 'CLOSED')",
            name="chk_payment_status",
        ),
        CheckConstraint("amount > 0", name="chk_positive_amount"),
        Index("idx_payment_failure_merchant", "merchant_id"),
        Index("idx_payment_failure_customer", "customer_id"),
        Index("idx_payment_failure_status", "status"),
        Index("idx_payment_failure_created", text("created_at DESC")),
        Index("idx_payment_failure_event_dedup", "webhook_event_id",
              unique=True),
    )

    failure_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    payment_id: Mapped[str] = mapped_column(String(255), unique=True)
    order_id: Mapped[str] = mapped_column(String(255))
    merchant_id: Mapped[str] = mapped_column(String(255))
    customer_id: Mapped[str] = mapped_column(String(255))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    error_code: Mapped[str] = mapped_column(String(255))
    error_description: Mapped[str] = mapped_column(Text)
    payment_method: Mapped[str] = mapped_column(String(50))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    webhook_event_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(50), server_default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class FailureRecoveryAction(Base):
    __tablename__ = "failure_recovery_action"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('AUTO_RETRY', 'SMS_CARD_UPDATE', "
            "'OFFER_INSTALLMENTS', 'ESCALATE_MANUAL')",
            name="chk_action_type",
        ),
        CheckConstraint(
            "action_status IN ('PENDING', 'EXECUTING', 'SUCCESS', 'FAILED')",
            name="chk_action_status",
        ),
        Index("idx_action_failure", "failure_id"),
        Index("idx_action_merchant", "merchant_id"),
        Index("idx_action_status", "action_status"),
        Index("idx_action_type", "action_type"),
        Index("idx_action_created", text("created_at DESC")),
        Index("idx_action_idempotency", "idempotency_key", unique=True),
    )

    action_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    failure_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_failure_event.failure_id", ondelete="CASCADE")
    )
    payment_id: Mapped[str] = mapped_column(String(255))
    merchant_id: Mapped[str] = mapped_column(String(255))
    customer_id: Mapped[str] = mapped_column(String(255))
    action_type: Mapped[str] = mapped_column(String(50))
    action_status: Mapped[str] = mapped_column(
        String(50), server_default="PENDING"
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'"), default=dict
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('FAILURE_DETECTED', 'WEBHOOK_DUPLICATE', "
            "'DIAGNOSIS_COMPLETE', 'POLICY_CHECK_PASSED', "
            "'POLICY_CHECK_FAILED', 'STRATEGY_SELECTED', 'ACTION_EXECUTING', "
            "'ACTION_SUCCESS', 'ACTION_FAILED', 'ESCALATED', "
            "'OUTCOME_RECORDED', 'ERROR_OCCURRED')",
            name="chk_event_type",
        ),
        Index("idx_audit_payment", "payment_id"),
        Index("idx_audit_failure", "failure_id"),
        Index("idx_audit_action", "action_id"),
        Index("idx_audit_merchant", "merchant_id"),
        Index("idx_audit_timestamp", text("timestamp DESC")),
        Index("idx_audit_event_type", "event_type"),
    )

    audit_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    payment_id: Mapped[str] = mapped_column(String(255))
    failure_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_failure_event.failure_id", ondelete="SET NULL")
    )
    action_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("failure_recovery_action.action_id", ondelete="SET NULL")
    )
    merchant_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'"), default=dict
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_key"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="chk_expires"),
        Index("idx_idempotency_payment", "payment_id"),
        Index("idx_idempotency_expires", "expires_at"),
    )

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(255))
    operation_type: Mapped[str] = mapped_column(String(100))
    result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'"), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class MerchantPolicy(Base):
    __tablename__ = "merchant_policy"
    __table_args__ = (
        CheckConstraint("max_retries > 0", name="chk_max_retries"),
        CheckConstraint(
            "daily_sms_limit_per_customer > 0", name="chk_daily_sms_limit"
        ),
        Index("idx_policy_merchant", "merchant_id"),
    )

    policy_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    merchant_id: Mapped[str] = mapped_column(String(255), unique=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), default=True
    )
    allowed_failure_types: Mapped[str] = mapped_column(Text)
    max_retries: Mapped[int] = mapped_column(
        Integer, server_default=text("5"), default=5
    )
    retry_delays_seconds: Mapped[str] = mapped_column(Text)
    sms_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), default=True
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), default=True
    )
    installments_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), default=True
    )
    callback_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), default=True
    )
    manual_escalation_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), default=True
    )
    daily_sms_limit_per_customer: Mapped[int] = mapped_column(
        Integer, server_default=text("3"), default=3
    )
    max_recovery_amount_per_payment: Mapped[int | None] = mapped_column(
        Integer
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CustomerRecord(Base):
    __tablename__ = "customer_record"
    __table_args__ = (
        Index("idx_customer_merchant", "merchant_id"),
        Index("idx_customer_risk", "is_high_risk"),
    )

    customer_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(255))
    account_created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    total_payment_attempts: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )
    successful_attempts: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )
    estimated_account_balance: Mapped[int | None] = mapped_column(Integer)
    is_high_risk: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), default=False
    )
    high_risk_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SMSDeliveryTracking(Base):
    __tablename__ = "sms_delivery_tracking"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SENT', 'DELIVERED', 'FAILED', 'CLICKED')",
            name="chk_sms_status",
        ),
        Index("idx_sms_action", "action_id"),
        Index("idx_sms_payment", "payment_id"),
        Index("idx_sms_customer", "customer_id"),
        Index("idx_sms_status", "status"),
    )

    sms_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    action_id: Mapped[UUID] = mapped_column(
        ForeignKey("failure_recovery_action.action_id", ondelete="CASCADE")
    )
    payment_id: Mapped[str] = mapped_column(String(255))
    customer_id: Mapped[str] = mapped_column(String(255))
    merchant_id: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(20))
    message_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), server_default="SENT")
    delivery_timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    click_timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    provider: Mapped[str | None] = mapped_column(String(50))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class OutcomeRecord(Base):
    __tablename__ = "outcome_record"
    __table_args__ = (
        CheckConstraint(
            "outcome_type IN ('SMS_SENT', 'SMS_DELIVERED', 'SMS_FAILED', "
            "'SMS_CLICKED', 'RETRY_ATTEMPTED', 'RETRY_SUCCESS', "
            "'RETRY_FAILED', 'EMI_OFFERED', 'EMI_ACCEPTED', 'EMI_REJECTED', "
            "'ESCALATED', 'MANUAL_RESOLVED')",
            name="chk_outcome_type",
        ),
        Index("idx_outcome_payment", "payment_id"),
        Index("idx_outcome_failure", "failure_id"),
        Index("idx_outcome_action", "action_id"),
        Index("idx_outcome_merchant", "merchant_id"),
        Index("idx_outcome_type", "outcome_type"),
        Index("idx_outcome_recorded", text("recorded_at DESC")),
    )

    outcome_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    payment_id: Mapped[str] = mapped_column(String(255))
    failure_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_failure_event.failure_id", ondelete="CASCADE")
    )
    action_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("failure_recovery_action.action_id", ondelete="SET NULL")
    )
    merchant_id: Mapped[str] = mapped_column(String(255))
    outcome_type: Mapped[str] = mapped_column(String(100))
    success: Mapped[bool] = mapped_column(Boolean)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'"), default=dict
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class SupportEscalation(Base):
    __tablename__ = "support_escalation"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')",
            name="chk_escalation_status",
        ),
        Index("idx_escalation_failure", "failure_id"),
        Index("idx_escalation_merchant", "merchant_id"),
        Index("idx_escalation_status", "status"),
        Index("idx_escalation_created", text("created_at DESC")),
    )

    escalation_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    failure_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_failure_event.failure_id", ondelete="CASCADE")
    )
    action_id: Mapped[UUID] = mapped_column(
        ForeignKey("failure_recovery_action.action_id", ondelete="CASCADE")
    )
    payment_id: Mapped[str] = mapped_column(String(255))
    merchant_id: Mapped[str] = mapped_column(String(255))
    customer_id: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    ticket_id: Mapped[str | None] = mapped_column(String(255))
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), server_default="OPEN")
    resolved_amount: Mapped[int | None] = mapped_column(Integer)
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class DiagnosisCache(Base):
    __tablename__ = "diagnosis_cache"
    __table_args__ = (
        CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="chk_confidence"
        ),
        Index("idx_diagnosis_cache_hash", "error_code_description_hash",
              unique=True),
        Index("idx_diagnosis_cache_expires", "expires_at"),
    )

    cache_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    error_code_description_hash: Mapped[str] = mapped_column(
        String(255), unique=True
    )
    failure_type: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Numeric(3, 2))
    recoverable: Mapped[bool] = mapped_column(Boolean)
    reasoning: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)
