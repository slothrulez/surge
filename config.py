"""
Configuration and constants for Payment Recovery System
Phase 0: Interfaces & Config
Reference: Blueprint Part 2 (Architecture), Part 11 (Deployment)

CRITICAL: Error code mapping is deterministic and cannot be changed by AI
(Blueprint line 1404: "LLM decides whether to charge the customer" is forbidden)
"""

import os
import json
from typing import Dict, List
from dotenv import load_dotenv
from models import FailureType

load_dotenv()


# ============================================================================
# ERROR CODE → FAILURE TYPE MAPPING (Blueprint lines 155-166)
# DETERMINISTIC: No AI overrides. This mapping is the source of truth.
# ============================================================================

ERROR_CODE_MAPPING: Dict[tuple, FailureType] = {
    # (error_code, error_description_substring) → FailureType
    
    ("BAD_REQUEST_ERROR", "Card has expired"): FailureType.CARD_EXPIRED,
    ("BAD_REQUEST_ERROR", "Expired"): FailureType.CARD_EXPIRED,
    ("BAD_REQUEST_ERROR", "Invalid expiry"): FailureType.CARD_EXPIRED,
    
    ("BAD_REQUEST_ERROR", "Insufficient funds"): FailureType.INSUFFICIENT_BALANCE,
    ("BAD_REQUEST_ERROR", "Insufficient balance"): FailureType.INSUFFICIENT_BALANCE,
    ("BAD_REQUEST_ERROR", "Not enough balance"): FailureType.INSUFFICIENT_BALANCE,
    
    ("BAD_REQUEST_ERROR", "Transaction limit exceeded"): FailureType.DAILY_LIMIT_HIT,
    ("BAD_REQUEST_ERROR", "Daily limit exceeded"): FailureType.DAILY_LIMIT_HIT,
    ("BAD_REQUEST_ERROR", "Limit reached"): FailureType.DAILY_LIMIT_HIT,
    
    ("GATEWAY_ERROR", "Request timeout"): FailureType.TIMEOUT,
    ("GATEWAY_ERROR", "Timeout"): FailureType.TIMEOUT,
    ("GATEWAY_ERROR", "Connection timeout"): FailureType.TIMEOUT,
    
    ("GATEWAY_ERROR", "Failed to connect to gateway"): FailureType.NETWORK_ERROR,
    ("GATEWAY_ERROR", "Network error"): FailureType.NETWORK_ERROR,
    ("GATEWAY_ERROR", "Connection refused"): FailureType.NETWORK_ERROR,
    
    ("BAD_REQUEST_ERROR", "Fraud check failed"): FailureType.FRAUD_FLAG,
    ("BAD_REQUEST_ERROR", "Fraud detection"): FailureType.FRAUD_FLAG,
    ("BAD_REQUEST_ERROR", "Suspicious transaction"): FailureType.FRAUD_FLAG,
    
    ("AUTHORIZATION_FAILED", "Issuer declined"): FailureType.ISSUER_DECLINED,
    ("AUTHORIZATION_FAILED", "Declined"): FailureType.ISSUER_DECLINED,
    ("AUTHORIZATION_FAILED", "Authorization failed"): FailureType.ISSUER_DECLINED,
    
    ("BAD_REQUEST_ERROR", "Account closed"): FailureType.ACCOUNT_CLOSED,
    ("BAD_REQUEST_ERROR", "Account closed or restricted"): FailureType.ACCOUNT_CLOSED,
    ("BAD_REQUEST_ERROR", "Account restricted"): FailureType.ACCOUNT_CLOSED,
    
    ("SERVER_ERROR", "Internal server error"): FailureType.INTERNAL_ERROR,
    ("SERVER_ERROR", "Server error"): FailureType.INTERNAL_ERROR,
    ("SERVER_ERROR", "Something went wrong"): FailureType.INTERNAL_ERROR,
}


def get_failure_type_from_razorpay_error(
    error_code: str, error_description: str
) -> FailureType:
    """
    Map Razorpay error to FailureType using exact deterministic mapping.
    
    This function is Task 52 from decomposition.
    CRITICAL: No ML/heuristics. Pure lookup table.
    
    Args:
        error_code: Razorpay error code (e.g., "BAD_REQUEST_ERROR")
        error_description: Razorpay error description
    
    Returns:
        FailureType enum value
    
    Reference: Blueprint lines 155-166
    """
    # Try exact match first
    key = (error_code, error_description)
    if key in ERROR_CODE_MAPPING:
        return ERROR_CODE_MAPPING[key]
    
    # Try partial match on error_code + description substring
    for (code, desc_pattern), failure_type in ERROR_CODE_MAPPING.items():
        if code == error_code and desc_pattern.lower() in error_description.lower():
            return failure_type
    
    # No match found
    return FailureType.UNKNOWN


# ============================================================================
# RETRY STRATEGY (Blueprint lines 219-222)
# DETERMINISTIC: Fixed delays, enforced by policy engine
# ============================================================================

DEFAULT_RETRY_CONFIG = {
    "max_retries": 5,
    "retry_delays_seconds": [60, 300, 900, 3600, 86400],  # 1m, 5m, 15m, 1h, 24h
}


# ============================================================================
# POLICY DEFAULTS (Blueprint lines 207-275)
# ============================================================================

DEFAULT_MERCHANT_RECOVERY_CONFIG = {
    "enabled": True,
    "allowed_failure_types": [
        FailureType.INSUFFICIENT_BALANCE.value,
        FailureType.CARD_EXPIRED.value,
        FailureType.TIMEOUT.value,
        FailureType.DAILY_LIMIT_HIT.value,
        FailureType.ISSUER_DECLINED.value,
        FailureType.NETWORK_ERROR.value,
        FailureType.INTERNAL_ERROR.value,
    ],
    "retry_config": DEFAULT_RETRY_CONFIG,
    "sms_enabled": True,
    "email_enabled": True,
    "installments_enabled": True,
    "callback_enabled": True,
    "manual_escalation_enabled": True,
    "daily_sms_limit_per_customer": 3,
    "max_recovery_amount_per_payment": None,  # No limit
}

# Failure types that are NEVER eligible for automatic recovery
UNRECOVERABLE_FAILURE_TYPES = [
    FailureType.FRAUD_FLAG,
    FailureType.ACCOUNT_CLOSED,
]


# ============================================================================
# CUSTOMER POLICY (Blueprint lines 234-275)
# ============================================================================

CUSTOMER_RISK_THRESHOLDS = {
    "account_age_days_high_risk": 1,  # < 1 day old account = high risk
    "max_failed_attempts_before_risk": 5,  # > 5 failures = high risk
    "min_success_rate_for_trust": 0.7,  # < 70% success rate = high risk
}

CUSTOMER_POLICY_RULES = {
    # high_risk customer → allowed actions (less aggressive)
    "high_risk_allowed_actions": [
        "SMS_CARD_UPDATE",  # Just inform
        "ESCALATE_MANUAL",  # Let human decide
    ],
    # normal customer → allowed actions (more aggressive)
    "normal_allowed_actions": [
        "AUTO_RETRY",
        "SMS_CARD_UPDATE",
        "OFFER_INSTALLMENTS",
        "ESCALATE_MANUAL",
    ],
}


# ============================================================================
# SMS THROTTLING (Blueprint line 228)
# DETERMINISTIC: Enforced in policy engine, no override
# ============================================================================

SMS_THROTTLE_RULES = {
    "daily_limit_per_customer": 3,
    "time_window_hours": 24,
}


# ============================================================================
# IDEMPOTENCY (Blueprint line 74)
# DETERMINISTIC: All operations must have idempotency_key
# ============================================================================

IDEMPOTENCY_EXPIRY_SECONDS = 86400 * 7  # 7 days


# ============================================================================
# AUDIT LOGGING (Blueprint line 76)
# DETERMINISTIC: Every decision logged
# ============================================================================

AUDIT_LOG_EVENTS = {
    "FAILURE_DETECTED": "Payment failure webhook received and validated",
    "WEBHOOK_DUPLICATE": "Duplicate webhook skipped by idempotency check",
    "DIAGNOSIS_COMPLETE": "Failure diagnosed and classified",
    "POLICY_CHECK_PASSED": "Merchant + customer policy check passed",
    "POLICY_CHECK_FAILED": "Policy check failed, recovery not allowed",
    "STRATEGY_SELECTED": "Recovery strategy selected",
    "ACTION_EXECUTING": "Recovery action starting execution",
    "ACTION_SUCCESS": "Recovery action succeeded",
    "ACTION_FAILED": "Recovery action failed",
    "ESCALATED": "Failure escalated to manual review",
    "OUTCOME_RECORDED": "Outcome recorded",
    "ERROR_OCCURRED": "Error during recovery",
}

AUDIT_LOG_ACTORS = {
    "SYSTEM": "System (scheduler, webhooks)",
    "DETECTION_ENGINE": "Detection Engine (webhook validation)",
    "DIAGNOSIS_ENGINE": "Diagnosis Engine (error classification)",
    "POLICY_ENGINE": "Policy Engine (eligibility check)",
    "STRATEGY_SELECTOR": "Strategy Selector (action ranking)",
    "ACTION_EXECUTOR": "Action Executor (execution)",
    "OUTCOME_TRACKER": "Outcome Tracker (result recording)",
}


# ============================================================================
# ENVIRONMENT VARIABLES (Phase 1: Project Setup)
# Reference: Blueprint Part 11 (Deployment)
# ============================================================================

class Settings:
    """Load and validate environment configuration"""
    
    # API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_VERSION: str = "1.0.0"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:password@localhost:5432/payment_recovery"
    )
    
    # Redis (for queues and caching)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Razorpay (Blueprint Part 2)
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    RAZORPAY_API_URL: str = "https://api.razorpay.com"
    
    # SMS Provider
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "twilio")  # twilio, msg91, razorpay
    SMS_ACCOUNT_SID: str = os.getenv("SMS_ACCOUNT_SID", "")
    SMS_AUTH_TOKEN: str = os.getenv("SMS_AUTH_TOKEN", "")
    SMS_FROM_NUMBER: str = os.getenv("SMS_FROM_NUMBER", "")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Feature Flags (Blueprint Part 8: Safety Rules)
    ENABLE_AUTO_RETRY: bool = os.getenv("ENABLE_AUTO_RETRY", "true").lower() == "true"
    ENABLE_SMS: bool = os.getenv("ENABLE_SMS", "true").lower() == "true"
    ENABLE_INSTALLMENTS: bool = os.getenv("ENABLE_INSTALLMENTS", "true").lower() == "true"
    
    # Safety limits
    MAX_RETRIES_GLOBAL: int = int(os.getenv("MAX_RETRIES_GLOBAL", "5"))
    MAX_SMS_PER_CUSTOMER_PER_DAY: int = int(os.getenv("MAX_SMS_PER_CUSTOMER_PER_DAY", "3"))
    
    def __init__(self):
        """Validate critical settings on startup"""
        if not self.RAZORPAY_KEY_ID or not self.RAZORPAY_KEY_SECRET:
            raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set")
        if not self.RAZORPAY_WEBHOOK_SECRET:
            raise ValueError("RAZORPAY_WEBHOOK_SECRET must be set")


# Global settings instance
settings = Settings()


# ============================================================================
# METRICS TARGETS (Blueprint Part 10: Metrics & Success Criteria)
# ============================================================================

METRICS_TARGETS = {
    "overall_recovery_rate": 0.60,  # 60-70%
    "recovery_by_failure_type": {
        FailureType.INSUFFICIENT_BALANCE.value: 0.70,
        FailureType.CARD_EXPIRED.value: 0.75,
        FailureType.TIMEOUT.value: 0.95,
        FailureType.FRAUD_FLAG.value: 0.20,
    },
    "action_effectiveness": {
        "SMS_CARD_UPDATE": {
            "click_through_rate": 0.70,
            "success_rate": 0.90,
        },
        "OFFER_INSTALLMENTS": {
            "acceptance_rate": 0.80,
            "success_rate": 0.90,
        },
        "AUTO_RETRY": {
            "success_rate": 0.95,
            "avg_retries_to_success": 1.5,
        },
    },
    "escalation_rate": 0.20,  # < 20%
    "average_recovery_time_seconds": 7200,  # < 2 hours
}


# ============================================================================
# Confidence Scoring (Blueprint line 197)
# Used in diagnosis but deterministic
# ============================================================================

CONFIDENCE_SCORES = {
    FailureType.CARD_EXPIRED: 0.95,  # Error code explicitly states this
    FailureType.INSUFFICIENT_BALANCE: 0.95,
    FailureType.TIMEOUT: 0.90,  # Network issues can have various causes
    FailureType.NETWORK_ERROR: 0.90,
    FailureType.INTERNAL_ERROR: 0.85,  # Could be many things
    FailureType.ISSUER_DECLINED: 0.92,
    FailureType.FRAUD_FLAG: 0.95,
    FailureType.ACCOUNT_CLOSED: 0.95,
    FailureType.DAILY_LIMIT_HIT: 0.95,
    FailureType.UNKNOWN: 0.50,  # No clear match
}
