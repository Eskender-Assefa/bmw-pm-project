"""Keep record-level serious concern flags on relevant safety and driving aspects."""
from alembic import op
revision='003_critical_scope'
down_revision='002_search_integrity'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("UPDATE aspects SET critical=0 WHERE feature_id IN (SELECT id FROM features WHERE category NOT IN ('C04','C09') AND id != 'drivetrain')")

def downgrade():
    # Old over-broad flags are intentionally not reconstructed.
    pass
