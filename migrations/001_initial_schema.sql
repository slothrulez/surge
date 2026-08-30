-- Payment Recovery System - Initial Schema
-- Phase 0: Database Layer
-- Reference: Blueprint Part 2 (System Architecture), Part 11 (Deployment)
-- This migration defines the complete schema for audit, idempotency, and recovery tracking

-- ============================================================================
-- TABLE: payment_failure_event
-- Stores each detected payment failure from Razorpay webhooks
-- ============================================================================
CREATE TABLE payment_failure_event (
    failure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id VARCHAR(255) NOT NULL UNIQUE,
    order_id VARCHAR(255) NOT NULL,
    merchant_id VARCHAR(255) NOT NULL,
    customer_id VARCHAR(255) NOT NULL,
    amount INTEGER NOT NULL,  -- in smallest currency unit (paisa)
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    
    -- Failure details from Razorpay webhook
    error_code VARCHAR(255) NOT NULL,  -- e.g., "BAD_REQUEST_ERROR"
    error_description TEXT NOT NULL,  -- e.g., "Card has expired"
    payment_method VARCHAR(50) NOT NULL,  -- "card", "upi", etc
    
    -- Detection metadata
    detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
    webhook_event_id VARCHAR(255) NOT NULL UNIQUE,  -- For deduplication
    
    -- Recovery attempt tracking
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',  -- PENDING, DIAGNOSED, POLICY_CHECK_PASSED, etc
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_payment_status CHECK (status IN (
        'PENDING', 'DIAGNOSED', 'POLICY_CHECK_PASSED', 'POLICY_CHECK_FAILED',
        'STRATEGY_SELECTED', 'ACTION_EXECUTING', 'ACTION_SUCCESS', 'ACTION_FAILED',
        'ESCALATED', 'CLOSED'
    )),
    CONSTRAINT chk_positive_amount CHECK (amount > 0)
);

CREATE INDEX idx_payment_failure_merchant ON payment_failure_event(merchant_id);
CREATE INDEX idx_payment_failure_customer ON payment_failure_event(customer_id);
CREATE INDEX idx_payment_failure_status ON payment_failure_event(status);
CREATE INDEX idx_payment_failure_created ON payment_failure_event(created_at DESC);
CREATE UNIQUE INDEX idx_payment_failure_event_dedup ON payment_failure_event(webhook_event_id);


-- ============================================================================
-- TABLE: failure_recovery_action
-- Tracks each recovery action attempt (retry, SMS, EMI offer, escalation)
-- Blueprint line 72: "Action Executor — send SMS, retry, create EMI, escalate"
-- ============================================================================
CREATE TABLE failure_recovery_action (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    failure_id UUID NOT NULL REFERENCES payment_failure_event(failure_id) ON DELETE CASCADE,
    payment_id VARCHAR(255) NOT NULL,
    merchant_id VARCHAR(255) NOT NULL,
    customer_id VARCHAR(255) NOT NULL,
    
    -- Action type and configuration
    action_type VARCHAR(50) NOT NULL,  -- AUTO_RETRY, SMS_CARD_UPDATE, OFFER_INSTALLMENTS, ESCALATE_MANUAL
    action_status VARCHAR(50) NOT NULL DEFAULT 'PENDING',  -- PENDING, EXECUTING, SUCCESS, FAILED
    
    -- Idempotency (Blueprint line 74)
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    
    -- Action details (JSON for flexibility)
    config JSONB NOT NULL DEFAULT '{}',  -- Action-specific config
    result JSONB,  -- Result after execution
    error_message TEXT,
    
    -- Timing
    scheduled_at TIMESTAMP,
    executed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_action_type CHECK (action_type IN (
        'AUTO_RETRY', 'SMS_CARD_UPDATE', 'OFFER_INSTALLMENTS', 'ESCALATE_MANUAL'
    )),
    CONSTRAINT chk_action_status CHECK (action_status IN (
        'PENDING', 'EXECUTING', 'SUCCESS', 'FAILED'
    ))
);

CREATE INDEX idx_action_failure ON failure_recovery_action(failure_id);
CREATE INDEX idx_action_merchant ON failure_recovery_action(merchant_id);
CREATE INDEX idx_action_status ON failure_recovery_action(action_status);
CREATE INDEX idx_action_type ON failure_recovery_action(action_type);
CREATE INDEX idx_action_created ON failure_recovery_action(created_at DESC);
CREATE UNIQUE INDEX idx_action_idempotency ON failure_recovery_action(idempotency_key);


-- ============================================================================
-- TABLE: audit_log
-- Complete audit trail of all decisions and actions
-- Blueprint line 76: "Audit Logger — log everything"
-- ============================================================================
CREATE TABLE audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id VARCHAR(255) NOT NULL,
    failure_id UUID REFERENCES payment_failure_event(failure_id) ON DELETE SET NULL,
    action_id UUID REFERENCES failure_recovery_action(action_id) ON DELETE SET NULL,
    merchant_id VARCHAR(255) NOT NULL,
    
    -- Event details
    event_type VARCHAR(100) NOT NULL,  -- FAILURE_DETECTED, DIAGNOSIS_COMPLETE, POLICY_CHECK, ACTION_EXECUTED, etc
    actor VARCHAR(100) NOT NULL,  -- SYSTEM, AI_DIAGNOSIS, POLICY_ENGINE, ACTION_EXECUTOR
    
    -- Full context (audit trail must be complete)
    details JSONB NOT NULL DEFAULT '{}',  -- Full decision context
    
    -- Timestamp
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_event_type CHECK (event_type IN (
        'FAILURE_DETECTED', 'WEBHOOK_DUPLICATE', 'DIAGNOSIS_COMPLETE',
        'POLICY_CHECK_PASSED', 'POLICY_CHECK_FAILED', 'STRATEGY_SELECTED',
        'ACTION_EXECUTING', 'ACTION_SUCCESS', 'ACTION_FAILED', 'ESCALATED',
        'OUTCOME_RECORDED', 'ERROR_OCCURRED'
    ))
);

CREATE INDEX idx_audit_payment ON audit_log(payment_id);
CREATE INDEX idx_audit_failure ON audit_log(failure_id);
CREATE INDEX idx_audit_action ON audit_log(action_id);
CREATE INDEX idx_audit_merchant ON audit_log(merchant_id);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_event_type ON audit_log(event_type);


-- ============================================================================
-- TABLE: idempotency_key
-- Tracks idempotent operations to prevent double-execution
-- Blueprint line 74: "Idempotency Handler — track state, prevent double-execution"
-- ============================================================================
CREATE TABLE idempotency_key (
    key VARCHAR(255) PRIMARY KEY,
    payment_id VARCHAR(255) NOT NULL,
    operation_type VARCHAR(100) NOT NULL,  -- WEBHOOK_RECEIVED, ACTION_EXECUTED, etc
    
    -- Result from first execution
    result JSONB NOT NULL DEFAULT '{}',
    
    -- Timing
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,  -- Garbage collection after expiry
    
    CONSTRAINT chk_expires CHECK (expires_at > created_at)
);

CREATE INDEX idx_idempotency_payment ON idempotency_key(payment_id);
CREATE INDEX idx_idempotency_expires ON idempotency_key(expires_at);


-- ============================================================================
-- TABLE: merchant_policy
-- Merchant-configured recovery policies
-- Blueprint lines 207-232: "Merchant policy: (set by merchant during onboarding or via UI)"
-- ============================================================================
CREATE TABLE merchant_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id VARCHAR(255) NOT NULL UNIQUE,
    
    -- Recovery enablement
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Allowed failure types (stored as comma-separated for flexibility)
    allowed_failure_types TEXT NOT NULL,  -- "INSUFFICIENT_BALANCE,CARD_EXPIRED,TIMEOUT,..."
    
    -- Retry policy
    max_retries INTEGER NOT NULL DEFAULT 5,
    retry_delays_seconds TEXT NOT NULL,  -- JSON array: [60, 300, 900, 3600, 86400]
    
    -- Channel enablement
    sms_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    installments_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    callback_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    manual_escalation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Limits
    daily_sms_limit_per_customer INTEGER NOT NULL DEFAULT 3,
    max_recovery_amount_per_payment INTEGER,  -- NULL = no limit
    
    -- Tracking
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_max_retries CHECK (max_retries > 0),
    CONSTRAINT chk_daily_sms_limit CHECK (daily_sms_limit_per_customer > 0)
);

CREATE INDEX idx_policy_merchant ON merchant_policy(merchant_id);


-- ============================================================================
-- TABLE: customer_record
-- Customer history for risk assessment (Blueprint line 176-190)
-- ============================================================================
CREATE TABLE customer_record (
    customer_id VARCHAR(255) PRIMARY KEY,
    merchant_id VARCHAR(255) NOT NULL,
    
    -- Account age
    account_created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Failure history
    total_payment_attempts INTEGER NOT NULL DEFAULT 0,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    successful_attempts INTEGER NOT NULL DEFAULT 0,
    
    -- Estimated balance (if available from bank data)
    estimated_account_balance INTEGER,
    
    -- Risk flag
    is_high_risk BOOLEAN NOT NULL DEFAULT FALSE,
    high_risk_reason TEXT,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customer_merchant ON customer_record(merchant_id);
CREATE INDEX idx_customer_risk ON customer_record(is_high_risk);


-- ============================================================================
-- TABLE: sms_delivery_tracking
-- SMS delivery and click tracking for outcome measurement (Blueprint line 442)
-- ============================================================================
CREATE TABLE sms_delivery_tracking (
    sms_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id UUID NOT NULL REFERENCES failure_recovery_action(action_id) ON DELETE CASCADE,
    payment_id VARCHAR(255) NOT NULL,
    customer_id VARCHAR(255) NOT NULL,
    merchant_id VARCHAR(255) NOT NULL,
    
    -- SMS details
    phone_number VARCHAR(20) NOT NULL,
    message_text TEXT NOT NULL,
    
    -- Delivery tracking
    status VARCHAR(50) NOT NULL DEFAULT 'SENT',  -- SENT, DELIVERED, FAILED, CLICKED
    delivery_timestamp TIMESTAMP,
    click_timestamp TIMESTAMP,
    
    -- Provider info
    provider VARCHAR(50),  -- "twilio", "msg91", etc
    provider_message_id VARCHAR(255),
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_sms_status CHECK (status IN ('SENT', 'DELIVERED', 'FAILED', 'CLICKED'))
);

CREATE INDEX idx_sms_action ON sms_delivery_tracking(action_id);
CREATE INDEX idx_sms_payment ON sms_delivery_tracking(payment_id);
CREATE INDEX idx_sms_customer ON sms_delivery_tracking(customer_id);
CREATE INDEX idx_sms_status ON sms_delivery_tracking(status);


-- ============================================================================
-- TABLE: outcome_record
-- Outcome tracking for each recovery attempt (Blueprint line 442-450)
-- ============================================================================
CREATE TABLE outcome_record (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id VARCHAR(255) NOT NULL,
    failure_id UUID NOT NULL REFERENCES payment_failure_event(failure_id) ON DELETE CASCADE,
    action_id UUID REFERENCES failure_recovery_action(action_id) ON DELETE SET NULL,
    merchant_id VARCHAR(255) NOT NULL,
    
    -- Outcome type
    outcome_type VARCHAR(100) NOT NULL,  -- SMS_SENT, SMS_DELIVERED, SMS_CLICKED, RETRY_ATTEMPTED, RETRY_SUCCESS, EMI_ACCEPTED, etc
    success BOOLEAN NOT NULL,
    
    -- Details
    details JSONB NOT NULL DEFAULT '{}',
    
    -- Timing
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_outcome_type CHECK (outcome_type IN (
        'SMS_SENT', 'SMS_DELIVERED', 'SMS_FAILED', 'SMS_CLICKED',
        'RETRY_ATTEMPTED', 'RETRY_SUCCESS', 'RETRY_FAILED',
        'EMI_OFFERED', 'EMI_ACCEPTED', 'EMI_REJECTED',
        'ESCALATED', 'MANUAL_RESOLVED'
    ))
);

CREATE INDEX idx_outcome_payment ON outcome_record(payment_id);
CREATE INDEX idx_outcome_failure ON outcome_record(failure_id);
CREATE INDEX idx_outcome_action ON outcome_record(action_id);
CREATE INDEX idx_outcome_merchant ON outcome_record(merchant_id);
CREATE INDEX idx_outcome_type ON outcome_record(outcome_type);
CREATE INDEX idx_outcome_recorded ON outcome_record(recorded_at DESC);


-- ============================================================================
-- TABLE: support_escalation
-- Manual escalation tickets (for ESCALATE_MANUAL action)
-- ============================================================================
CREATE TABLE support_escalation (
    escalation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    failure_id UUID NOT NULL REFERENCES payment_failure_event(failure_id) ON DELETE CASCADE,
    action_id UUID NOT NULL REFERENCES failure_recovery_action(action_id) ON DELETE CASCADE,
    payment_id VARCHAR(255) NOT NULL,
    merchant_id VARCHAR(255) NOT NULL,
    customer_id VARCHAR(255) NOT NULL,
    
    -- Escalation details
    reason TEXT NOT NULL,
    ticket_id VARCHAR(255),  -- External support system ticket ID
    assigned_to VARCHAR(255),  -- Support agent
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',  -- OPEN, IN_PROGRESS, RESOLVED, CLOSED
    
    -- Resolution
    resolved_amount INTEGER,  -- If manually refunded/recovered
    resolution_notes TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP,
    
    CONSTRAINT chk_escalation_status CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'))
);

CREATE INDEX idx_escalation_failure ON support_escalation(failure_id);
CREATE INDEX idx_escalation_merchant ON support_escalation(merchant_id);
CREATE INDEX idx_escalation_status ON support_escalation(status);
CREATE INDEX idx_escalation_created ON support_escalation(created_at DESC);


-- ============================================================================
-- TABLE: diagnosis_cache
-- Cache diagnosis results to avoid redundant analysis
-- ============================================================================
CREATE TABLE diagnosis_cache (
    cache_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_code_description_hash VARCHAR(255) NOT NULL UNIQUE,  -- Hash of error_code + error_description
    
    -- Cached diagnosis
    failure_type VARCHAR(50) NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL,
    recoverable BOOLEAN NOT NULL,
    reasoning TEXT NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,  -- Refresh cache periodically
    
    CONSTRAINT chk_confidence CHECK (confidence BETWEEN 0 AND 1)
);

CREATE INDEX idx_diagnosis_cache_hash ON diagnosis_cache(error_code_description_hash);
CREATE INDEX idx_diagnosis_cache_expires ON diagnosis_cache(expires_at);


-- ============================================================================
-- Constraints and Comments
-- ============================================================================

COMMENT ON TABLE payment_failure_event IS 'Core table: each payment failure from Razorpay. Blueprint line 85-127 (Webhook Receiver)';
COMMENT ON TABLE failure_recovery_action IS 'Recovery attempts: retry, SMS, EMI, escalation. Blueprint line 322-420 (Action Executor)';
COMMENT ON TABLE audit_log IS 'Complete audit trail of all decisions. Blueprint line 76 (Audit Logger)';
COMMENT ON TABLE idempotency_key IS 'Prevent double-execution. Blueprint line 74 (Idempotency Handler)';
COMMENT ON COLUMN payment_failure_event.status IS 'Tracks state through recovery pipeline. Blueprint line 133-148 (Detection Engine)';
COMMENT ON COLUMN failure_recovery_action.idempotency_key IS 'Deterministic hash to prevent double-execution of same action';
