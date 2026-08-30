"""
Data models for Payment Failure Auto-Responder
Defined in Phase 0: Interfaces & Config
Reference: Blueprint lines 155-166, 207-232
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS (Blueprint line 155-166, and policy sections)
# ============================================================================

class FailureType(str, Enum):
    """Failure classification from Razorpay error codes"""
    CARD_EXPIRED = "CARD_EXPIRED"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    DAILY_LIMIT_HIT = "DAILY_LIMIT_HIT"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    FRAUD_FLAG = "FRAUD_FLAG"
    ISSUER_DECLINED = "ISSUER_DECLINED"
    ACCOUNT_CLOSED = "ACCOUNT_CLOSED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    """Recovery actions available"""
    AUTO_RETRY = "AUTO_RETRY"
    SMS_CARD_UPDATE = "SMS_CARD_UPDATE"
    OFFER_INSTALLMENTS = "OFFER_INSTALLMENTS"
    ESCALATE_MANUAL = "ESCALATE_MANUAL"


class RecoveryStatus(str, Enum):
    """Status of recovery attempt"""
    PENDING = "PENDING"  # Failure detected, not yet diagnosed
    DIAGNOSED = "DIAGNOSED"  # Failure classified, awaiting policy check
    POLICY_CHECK_PASSED = "POLICY_CHECK_PASSED"  # Eligible for recovery
    POLICY_CHECK_FAILED = "POLICY_CHECK_FAILED"  # Not eligible
    STRATEGY_SELECTED = "STRATEGY_SELECTED"  # Action chosen
    ACTION_EXECUTING = "ACTION_EXECUTING"  # Action in progress
    ACTION_SUCCESS = "ACTION_SUCCESS"  # Action succeeded, payment recovered
    ACTION_FAILED = "ACTION_FAILED"  # Action executed but didn't recover payment
    ESCALATED = "ESCALATED"  # Sent to manual review
    CLOSED = "CLOSED"  # No further recovery possible


class SMSDeliveryStatus(str, Enum):
    """SMS delivery status (for outcome tracking)"""
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CLICKED = "CLICKED"  # Customer clicked recovery link in SMS


class PaymentMethodType(str, Enum):
    """Payment method used"""
    CARD = "card"
    UPI = "upi"
    WALLET = "wallet"
    BANK_TRANSFER = "bank_transfer"


# ============================================================================
# RAZORPAY WEBHOOK MODELS (Blueprint lines 89-118)
# ============================================================================

class AcquirerData(BaseModel):
    """Acquirer-level response data"""
    rrn: Optional[str] = None  # RRN (Retrieval Reference Number)
    auth_code: Optional[str] = None


class PaymentPayload(BaseModel):
    """Payment object in Razorpay webhook"""
    id: str  # payment ID
    order_id: str  # linked order ID
    amount: int  # amount in smallest currency unit (paisa for INR)
    currency: str  # "INR"
    status: str  # "failed", "created", "authorized"
    method: PaymentMethodType
    description: str
    error_code: str  # e.g., "BAD_REQUEST_ERROR"
    error_description: str  # e.g., "Card has expired"
    acquirer_data: AcquirerData
    vpa: Optional[str] = None  # UPI identifier
    email: str
    contact: str  # phone number
    notes: Optional[Dict[str, Any]] = None  # merchant custom data


class WebhookPayload(BaseModel):
    """Razorpay webhook event structure"""
    payment: PaymentPayload


class RazorpayWebhook(BaseModel):
    """Complete webhook from Razorpay (lines 89-118)"""
    event: str  # "payment.failed"
    created_at: int  # Unix timestamp
    payload: WebhookPayload


# ============================================================================
# DIAGNOSIS MODELS (Blueprint lines 150-201)
# ============================================================================

class CustomerSignals(BaseModel):
    """Customer-level signals for diagnosis (Blueprint lines 176-190)"""
    customer_age_days: int
    past_failed_attempts: int
    past_success_rate: float = Field(ge=0, le=1)
    account_balance_estimated: Optional[int] = None


class PaymentSignals(BaseModel):
    """Payment-level signals"""
    is_retry_attempt: bool
    payment_method_used: PaymentMethodType
    card_last_used_days_ago: Optional[int] = None


class TemporalSignals(BaseModel):
    """Time-based signals"""
    time_of_day: str  # HH:MM format
    day_of_week: str  # Monday, Tuesday, etc


class DiagnosisResult(BaseModel):
    """Output of diagnosis engine (Blueprint line 194-200)"""
    failure_type: FailureType
    confidence: float = Field(ge=0, le=1)  # 0-1 scale
    recoverable: bool
    reason: str
    customer_signals: Optional[CustomerSignals] = None
    payment_signals: Optional[PaymentSignals] = None
    temporal_signals: Optional[TemporalSignals] = None


# ============================================================================
# POLICY MODELS (Blueprint lines 203-275)
# ============================================================================

class RetryConfig(BaseModel):
    """Retry policy configuration"""
    max_retries: int
    retry_delays_seconds: List[int]  # e.g., [60, 300, 900, 3600, 86400]


class MerchantRecoveryConfig(BaseModel):
    """Merchant-level recovery policy (Blueprint lines 207-232)"""
    enabled: bool
    allowed_failure_types: List[FailureType]
    retry_config: RetryConfig
    sms_enabled: bool
    email_enabled: bool
    installments_enabled: bool
    callback_enabled: bool
    manual_escalation_enabled: bool
    daily_sms_limit_per_customer: int
    max_recovery_amount_per_payment: Optional[int] = None  # None = no limit


class MerchantPolicy(BaseModel):
    """Complete merchant policy"""
    merchant_id: str
    recovery_config: MerchantRecoveryConfig


class CustomerPolicyEvaluation(BaseModel):
    """Customer eligibility evaluation"""
    is_high_risk: bool
    reason: str
    allowed_actions: List[ActionType]


# ============================================================================
# STRATEGY MODELS (Blueprint lines 277-320)
# ============================================================================

class StrategyScore(BaseModel):
    """Score for a single strategy"""
    action_type: ActionType
    score: float = Field(ge=0, le=1)
    reasoning: str


class StrategySelectionResult(BaseModel):
    """Output of strategy selector"""
    selected_action: ActionType
    scores: List[StrategyScore]  # Sorted by score descending
    reasoning: str


# ============================================================================
# ACTION EXECUTION MODELS (Blueprint lines 322-420)
# ============================================================================

class ActionExecutionRequest(BaseModel):
    """Request to execute an action"""
    failure_id: str
    payment_id: str
    customer_id: str
    merchant_id: str
    action_type: ActionType
    action_config: Dict[str, Any]  # Action-specific params


class ActionExecutionResult(BaseModel):
    """Result of action execution"""
    action_id: str  # UUID assigned to this action
    payment_id: str
    action_type: ActionType
    success: bool
    status: str  # e.g., "SENT", "SCHEDULED", "FAILED"
    message: str
    executed_at: datetime
    idempotency_key: str  # For duplicate detection


# ============================================================================
# AUDIT & OUTCOME MODELS
# ============================================================================

class AuditLogEntry(BaseModel):
    """Audit trail entry (Blueprint line 76)"""
    audit_id: str  # UUID
    payment_id: str
    failure_id: Optional[str] = None
    action_id: Optional[str] = None
    event_type: str  # "FAILURE_DETECTED", "DIAGNOSIS_COMPLETE", "POLICY_CHECK", "ACTION_EXECUTED", etc
    actor: str  # "SYSTEM", "AI_DIAGNOSIS", "POLICY_ENGINE", "ACTION_EXECUTOR"
    details: Dict[str, Any]  # Full context
    timestamp: datetime
    merchant_id: str


class OutcomeRecord(BaseModel):
    """Outcome tracking entry"""
    outcome_id: str  # UUID
    payment_id: str
    failure_id: str
    action_id: Optional[str] = None
    outcome_type: str  # "SMS_SENT", "SMS_DELIVERED", "SMS_CLICKED", "RETRY_ATTEMPTED", "RETRY_SUCCESS", etc
    success: bool
    details: Dict[str, Any]
    recorded_at: datetime


class FailureRecoveryStatus(BaseModel):
    """Status of a single failure recovery attempt"""
    failure_id: str
    payment_id: str
    order_id: str
    merchant_id: str
    customer_id: str
    amount: int
    currency: str
    
    # Failure details
    failure_type: FailureType
    error_code: str
    error_description: str
    detected_at: datetime
    
    # Recovery attempt
    recovery_status: RecoveryStatus
    diagnosis: Optional[DiagnosisResult] = None
    selected_action: Optional[ActionType] = None
    action_id: Optional[str] = None
    
    # Outcome
    recovered: bool = False
    recovery_amount: Optional[int] = None
    recovered_at: Optional[datetime] = None
    
    # Audit
    created_at: datetime
    updated_at: datetime


# ============================================================================
# IDEMPOTENCY MODELS
# ============================================================================

class IdempotencyKey(BaseModel):
    """Idempotency tracking (Blueprint line 74)"""
    key: str  # Deterministic hash of operation
    payment_id: str
    operation_type: str  # "WEBHOOK_RECEIVED", "ACTION_EXECUTED", etc
    result: Dict[str, Any]  # The result we got
    created_at: datetime
    expires_at: datetime  # When to garbage collect


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check endpoint"""
    status: str
    timestamp: datetime
    version: str


class WebhookAckResponse(BaseModel):
    """Webhook receiver acknowledgment"""
    received: bool
    event_id: str
    timestamp: datetime


class MetricsResponse(BaseModel):
    """Metrics response (Blueprint Part 10)"""
    overall_recovery_rate: float
    revenue_recovered: int
    recovery_by_failure_type: Dict[FailureType, float]
    action_effectiveness: Dict[ActionType, Dict[str, float]]
    escalation_rate: float
    average_recovery_time_seconds: float
    sms_delivery_rate: float
    calculated_at: datetime
