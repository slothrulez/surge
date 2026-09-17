from pathlib import Path

from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the existing authoritative schema to an empty database."""
    schema = Path(__file__).resolve().parents[1] / "001_initial_schema.sql"
    op.execute(schema.read_text(encoding="utf-8"))


def downgrade() -> None:
    """Remove initial tables in reverse dependency order."""
    for table in (
        "diagnosis_cache",
        "support_escalation",
        "outcome_record",
        "sms_delivery_tracking",
        "customer_record",
        "merchant_policy",
        "idempotency_key",
        "audit_log",
        "failure_recovery_action",
        "payment_failure_event",
    ):
        op.drop_table(table)
