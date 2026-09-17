from io import StringIO
from pathlib import Path
import re

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


from datetime import datetime, timedelta

from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from src.database import queries
from src.database import connection
from src.database.models import Base


ROOT = Path(__file__).resolve().parents[1]


def test_create_database_engine_rejects_non_postgresql() -> None:
    """Only PostgreSQL URLs may create pooled engines."""
    with pytest.raises(RuntimeError, match="PostgreSQL URL"):
        connection.create_database_engine("sqlite://")


def test_engine_lifecycle_with_postgresql_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Engine creation is lazy, pooled, and disposable without connecting."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://localhost/test_database"
    )
    connection.dispose_engine()
    engine = connection.init_engine("postgresql://localhost/test_database")
    assert engine is connection.get_engine()
    assert engine.pool.status()
    factory = connection.get_session_factory()
    assert factory.kw["bind"] is engine
    assert factory.kw["autocommit"] is False
    connection.dispose_engine()
    with pytest.raises(RuntimeError, match="init_engine"):
        connection.get_engine()
    with pytest.raises(RuntimeError, match="init_engine"):
        connection.get_session_factory()


def test_declarative_base() -> None:
    """Verify all ORM mappings can share typed declarative metadata."""
    assert issubclass(Base, DeclarativeBase)
    assert isinstance(Base.metadata, MetaData)
    assert Base.registry.metadata is Base.metadata


@pytest.mark.parametrize("table_name", list(Base.metadata.tables))
def test_orm_matches_sql_schema(table_name: str) -> None:
    """Compare ORM columns and constraints with migration SQL."""
    schema = (ROOT / "migrations/001_initial_schema.sql").read_text(
        encoding="utf-8"
    )
    match = re.search(
        rf"CREATE TABLE {table_name} \((.*?)\n\);", schema, re.DOTALL
    )
    assert match is not None
    body = match.group(1)
    definitions = re.findall(
        r"^    (\w+) (UUID|VARCHAR\(\d+\)|TEXT|INTEGER|BOOLEAN|TIMESTAMP|"
        r"JSONB|NUMERIC\(\d+, \d+\))(.*)$", body, re.MULTILINE
    )
    table = Base.metadata.tables[table_name]
    assert list(table.columns.keys()) == [item[0] for item in definitions]
    for name, sql_type, suffix in definitions:
        column = table.c[name]
        compiled_type = str(column.type.compile(dialect=postgresql.dialect()))
        assert compiled_type.replace(" WITHOUT TIME ZONE", "") == sql_type
        assert column.nullable == (
            "NOT NULL" not in suffix and "PRIMARY KEY" not in suffix
        )
        assert column.primary_key == ("PRIMARY KEY" in suffix)
        if "UNIQUE" in suffix:
            assert column.unique
        if "DEFAULT" in suffix:
            assert column.server_default is not None
    constraint_names = set(re.findall(r"CONSTRAINT (\w+)", body))
    assert constraint_names == {
        constraint.name for constraint in table.constraints
        if constraint.name is not None
    }
    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert f"CREATE TABLE {table_name}" in ddl


def migration_config() -> Config:
    """Load migration configuration without connecting to a database."""
    return Config(str(ROOT / "alembic.ini"), output_buffer=StringIO())


def test_migration_revision_matches_initial_schema() -> None:
    """Verify the initial schema is the sole tracked revision."""
    scripts = ScriptDirectory.from_config(migration_config())
    assert scripts.get_current_head() == "001_initial_schema"
    assert len(list(scripts.walk_revisions())) == 1


def test_migration_upgrade_renders_all_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify offline upgrades render the authoritative ten-table schema."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test_database")
    config = migration_config()
    command.upgrade(config, "head", sql=True)
    assert isinstance(config.output_buffer, StringIO)
    sql = config.output_buffer.getvalue()
    schema = (ROOT / "migrations/001_initial_schema.sql").read_text(
        encoding="utf-8"
    )
    assert schema.strip() in sql
    assert sql.count("CREATE TABLE ") == 11
    assert "INSERT INTO alembic_version" in sql
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql


def test_migration_downgrade_reverses_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify rollback drops children before referenced tables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test_database")
    config = migration_config()
    command.downgrade(config, "001_initial_schema:base", sql=True)
    assert isinstance(config.output_buffer, StringIO)
    sql = config.output_buffer.getvalue()
    assert sql.count("DROP TABLE ") == 11
    assert sql.index("DROP TABLE audit_log") < sql.index(
        "DROP TABLE failure_recovery_action"
    )
    assert sql.index("DROP TABLE failure_recovery_action") < sql.index(
        "DROP TABLE payment_failure_event"
    )


def test_migration_requires_explicit_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent migrations from silently targeting application credentials."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        command.upgrade(migration_config(), "head", sql=True)


def test_migration_rejects_non_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject dialects incompatible with the production SQL schema."""
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    with pytest.raises(RuntimeError, match="require PostgreSQL"):
        command.upgrade(migration_config(), "head", sql=True)


@pytest.fixture()
def db_session():
    """Provide a transactional SQLite session with full ORM schema.

    SQLite cannot render PostgreSQL's JSONB, so the test dialect maps
    JSONB columns to its native JSON type for behavior verification.
    """
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    SQLiteTypeCompiler.visit_JSONB = SQLiteTypeCompiler.visit_JSON
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _sample_failure_kwargs() -> dict:
    """Build valid insert_payment_failure_event arguments."""
    return {
        "payment_id": "pay_test_1",
        "order_id": "order_test_1",
        "merchant_id": "merchant_1",
        "customer_id": "customer_1",
        "amount": 100000,
        "currency": "INR",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Card has expired",
        "payment_method": "card",
        "webhook_event_id": "evt_test_1",
        "detected_at": datetime(2026, 9, 17, 12, 0, 0),
    }


def _sample_action_kwargs(failure_id) -> dict:
    """Build valid insert_recovery_action arguments."""
    return {
        "failure_id": failure_id,
        "payment_id": "pay_test_1",
        "merchant_id": "merchant_1",
        "customer_id": "customer_1",
        "action_type": "SMS_CARD_UPDATE",
        "idempotency_key": "key_sms_test_1",
        "config": {"template": "card_update"},
    }


def test_insert_payment_failure_event_audits(db_session) -> None:
    """Insert creates the event plus a FAILURE_DETECTED audit entry."""
    with queries.transaction(db_session):
        failure_id = queries.insert_payment_failure_event(
            db_session, **_sample_failure_kwargs()
        )
    failure = queries.get_payment_failure_by_id(db_session, failure_id)
    assert failure is not None
    assert failure.status == "PENDING"
    assert failure.amount == 100000
    entries = db_session.query(queries.AuditLog).all()
    assert len(entries) == 1
    assert entries[0].event_type == "FAILURE_DETECTED"
    assert entries[0].details["error_code"] == "BAD_REQUEST_ERROR"


def test_insert_payment_failure_event_duplicate_rejected(
    db_session,
) -> None:
    """Duplicate payment_id or webhook_event_id raises typed error."""
    with queries.transaction(db_session):
        queries.insert_payment_failure_event(
            db_session, **_sample_failure_kwargs()
        )
    with pytest.raises(queries.DuplicateRecordError):
        with queries.transaction(db_session):
            queries.insert_payment_failure_event(
                db_session, **_sample_failure_kwargs()
            )


def test_update_failure_status_audits_transition(db_session) -> None:
    """Status changes record from/to context in the audit log."""
    with queries.transaction(db_session):
        failure_id = queries.insert_payment_failure_event(
            db_session, **_sample_failure_kwargs()
        )
        queries.update_failure_status(
            db_session, failure_id, "DIAGNOSED", "DIAGNOSIS_ENGINE",
            "Card expired mapped",
        )
    failure = queries.get_payment_failure_by_id(db_session, failure_id)
    assert failure is not None
    assert failure.status == "DIAGNOSED"
    events = [
        entry.event_type for entry in db_session.query(queries.AuditLog)
    ]
    assert events == ["FAILURE_DETECTED", "DIAGNOSIS_COMPLETE"]
    with pytest.raises(ValueError, match="not found"):
        with queries.transaction(db_session):
            queries.update_failure_status(
                db_session, "00000000-0000-0000-0000-000000000000",
                "CLOSED", "SYSTEM", "unknown id",
            )


def test_insert_recovery_action_idempotent(db_session) -> None:
    """Same idempotency key cannot create a second action."""
    with queries.transaction(db_session):
        failure_id = queries.insert_payment_failure_event(
            db_session, **_sample_failure_kwargs()
        )
        action_id = queries.insert_recovery_action(
            db_session, **_sample_action_kwargs(failure_id)
        )
    actions = queries.get_recovery_actions_for_failure(
        db_session, failure_id
    )
    assert len(actions) == 1
    assert actions[0].action_id == action_id
    assert actions[0].action_status == "PENDING"
    with pytest.raises(queries.DuplicateRecordError):
        with queries.transaction(db_session):
            queries.insert_recovery_action(
                db_session, **_sample_action_kwargs(failure_id)
            )


def test_idempotency_key_roundtrip_and_expiry(db_session) -> None:
    """Results are returned before expiry and invisible after it."""
    with queries.transaction(db_session):
        queries.record_idempotency_key(
            db_session, "op_1", "pay_test_1", "WEBHOOK_RECEIVED",
            {"event_id": "evt_test_1"},
        )
    assert queries.check_idempotency(db_session, "op_1") == {
        "event_id": "evt_test_1"
    }
    assert queries.check_idempotency(db_session, "missing") is None
    with queries.transaction(db_session):
        entry = db_session.query(queries.IdempotencyKey).one()
        entry.created_at = datetime.utcnow() - timedelta(days=8)
        entry.expires_at = datetime.utcnow() - timedelta(days=1)
    assert queries.check_idempotency(db_session, "op_1") is None


def test_log_audit_event_stores_full_context(db_session) -> None:
    """Audit entries persist actor, details and optional relations."""
    with queries.transaction(db_session):
        audit_id = queries.log_audit_event(
            db_session, "pay_test_1", "merchant_1",
            "FAILURE_DETECTED", "DETECTION_ENGINE", {"k": "v"},
        )
    entry = db_session.query(queries.AuditLog).one()
    assert entry.audit_id == audit_id
    assert entry.details == {"k": "v"}
    assert entry.actor == "DETECTION_ENGINE"


def test_merchant_policy_ensure_and_update(db_session) -> None:
    """Policy is created from defaults once and updated with audit."""
    defaults = {
        "enabled": True,
        "allowed_failure_types": "CARD_EXPIRED,TIMEOUT",
        "max_retries": 5,
        "retry_delays_seconds": "[60, 300]",
        "sms_enabled": True,
        "email_enabled": True,
        "installments_enabled": True,
        "callback_enabled": True,
        "manual_escalation_enabled": True,
        "daily_sms_limit_per_customer": 3,
        "max_recovery_amount_per_payment": None,
    }
    with queries.transaction(db_session):
        policy = queries.ensure_merchant_policy(
            db_session, "merchant_1", defaults
        )
        policy_again = queries.ensure_merchant_policy(
            db_session, "merchant_1", defaults
        )
        assert policy.policy_id == policy_again.policy_id
        updated = queries.update_merchant_policy(
            db_session, "merchant_1",
            {"daily_sms_limit_per_customer": 1}, "ADMIN",
        )
    assert updated.daily_sms_limit_per_customer == 1
    assert queries.get_merchant_policy(db_session, "merchant_1") is not None
    update_entries = [
        entry for entry in db_session.query(queries.AuditLog)
        if "policy_update" in entry.details
    ]
    assert len(update_entries) == 1
    assert update_entries[0].details["policy_update"]["before"][
        "daily_sms_limit_per_customer"
    ] == 3
    with pytest.raises(ValueError, match="not found"):
        with queries.transaction(db_session):
            queries.update_merchant_policy(
                db_session, "merchant_missing", {}, "ADMIN"
            )


def test_customer_record_ensure_and_fetch(db_session) -> None:
    """Customer records are created blank once and reused."""
    with queries.transaction(db_session):
        record = queries.ensure_customer_record(
            db_session, "customer_1", "merchant_1"
        )
        record_again = queries.ensure_customer_record(
            db_session, "customer_1", "merchant_1"
        )
    assert record.customer_id == record_again.customer_id
    assert record.total_payment_attempts == 0
    fetched = queries.get_customer_record(db_session, "customer_1")
    assert fetched is not None
    assert fetched.is_high_risk is False


def test_sms_outcome_escalation_flow(db_session) -> None:
    """SMS record, outcome recording and escalation work end-to-end."""
    with queries.transaction(db_session):
        failure_id = queries.insert_payment_failure_event(
            db_session, **_sample_failure_kwargs()
        )
        action_id = queries.insert_recovery_action(
            db_session, **_sample_action_kwargs(failure_id)
        )
        sms_id = queries.record_sms_delivery(
            db_session, action_id, "pay_test_1", "customer_1",
            "merchant_1", "+910000000000", "Update your card", "twilio",
            provider_message_id="sm_1",
        )
        outcome_id = queries.record_outcome(
            db_session, "pay_test_1", failure_id, "SMS_SENT", True,
            {"sms_id": str(sms_id)}, action_id=action_id,
        )
        escalation_id = queries.create_support_escalation(
            db_session, failure_id, action_id, "pay_test_1",
            "merchant_1", "customer_1", "Manual review required",
        )
    failure = queries.get_payment_failure_by_id(db_session, failure_id)
    assert failure is not None
    assert failure.status == "ACTION_SUCCESS"
    outcome = db_session.query(queries.OutcomeRecord).one()
    assert outcome.outcome_id == outcome_id
    assert outcome.success is True
    sms = db_session.query(queries.SMSDeliveryTracking).one()
    assert sms.sms_id == sms_id
    escalation = db_session.query(queries.SupportEscalation).one()
    assert escalation.escalation_id == escalation_id
    assert escalation.status == "OPEN"
    event_types = [
        entry.event_type for entry in db_session.query(queries.AuditLog)
    ]
    assert event_types == [
        "FAILURE_DETECTED", "ACTION_EXECUTING", "OUTCOME_RECORDED",
        "ESCALATED",
    ]


def test_record_outcome_failure_marks_action_failed(db_session) -> None:
    """Unsuccessful outcomes transition status to ACTION_FAILED."""
    with queries.transaction(db_session):
        failure_id = queries.insert_payment_failure_event(
            db_session, **_sample_failure_kwargs()
        )
        queries.record_outcome(
            db_session, "pay_test_1", failure_id, "RETRY_FAILED", False,
            {"reason": "gateway declined"},
        )
    failure = queries.get_payment_failure_by_id(db_session, failure_id)
    assert failure is not None
    assert failure.status == "ACTION_FAILED"
    with pytest.raises(ValueError, match="not found"):
        with queries.transaction(db_session):
            queries.record_outcome(
                db_session, "pay_missing",
                "00000000-0000-0000-0000-000000000000",
                "RETRY_FAILED", False, {},
            )


def test_diagnosis_cache_roundtrip_and_expiry(db_session) -> None:
    """Cached diagnoses expire and are re-insertable after expiry."""
    with queries.transaction(db_session):
        cache_id = queries.insert_diagnosis_cache(
            db_session, "hash_1", "CARD_EXPIRED", 0.95, True,
            "Deterministic mapping", ttl_seconds=3600,
        )
    cached = queries.get_diagnosis_cache(db_session, "hash_1")
    assert cached is not None
    assert cached.cache_id == cache_id
    assert float(cached.confidence) == 0.95
    with queries.transaction(db_session):
        entry = db_session.query(queries.DiagnosisCache).one()
        entry.created_at = datetime.utcnow() - timedelta(days=2)
        entry.expires_at = datetime.utcnow() - timedelta(days=1)
    assert queries.get_diagnosis_cache(db_session, "hash_1") is None
    with queries.transaction(db_session):
        queries.insert_diagnosis_cache(
            db_session, "hash_1", "CARD_EXPIRED", 0.95, True,
            "Deterministic mapping", ttl_seconds=3600,
        )
    assert queries.get_diagnosis_cache(db_session, "hash_1") is not None


def test_transaction_rolls_back_on_error(db_session) -> None:
    """Failures inside a transaction leave no partial writes."""
    with pytest.raises(queries.DatabaseError):
        with queries.transaction(db_session):
            queries.insert_payment_failure_event(
                db_session, **_sample_failure_kwargs()
            )
            raise queries.DatabaseError("simulated failure")
    assert db_session.query(
        queries.PaymentFailureEvent
    ).filter_by(payment_id="pay_test_1").count() == 0
    assert db_session.query(queries.AuditLog).count() == 0
