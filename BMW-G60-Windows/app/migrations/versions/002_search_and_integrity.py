"""Local evidence search and append-only guards."""
from alembic import op

revision = '002_search_integrity'
down_revision = '374f9139e8b2'
branch_labels = None
depends_on = None

TABLES = ('audit_events','requirement_revisions','priority_runs','decisions','analysis_runs','exports')

def upgrade():
    op.execute("CREATE VIRTUAL TABLE evidence_fts USING fts5(evidence_id UNINDEXED, text, tokenize='unicode61')")
    for table in TABLES:
        for operation in ('UPDATE','DELETE'):
            op.execute(f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only record'); END")

def downgrade():
    for table in TABLES:
        for operation in ('update','delete'):
            op.execute(f'DROP TRIGGER immutable_{table}_{operation}')
    op.execute('DROP TABLE evidence_fts')
