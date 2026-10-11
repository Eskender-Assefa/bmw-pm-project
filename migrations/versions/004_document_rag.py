"""Local document retrieval and review, without changing existing demand tables."""
from alembic import op
import sqlalchemy as sa

revision = '004_document_rag'
down_revision = '003_critical_scope'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('rag_chunks',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('evidence_id', sa.String(), sa.ForeignKey('evidence.id'), nullable=False),
        sa.Column('source_id', sa.String(), sa.ForeignKey('sources.id'), nullable=False),
        sa.Column('model', sa.String()),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('start', sa.Integer(), nullable=False),
        sa.Column('end', sa.Integer(), nullable=False),
        sa.Column('index_version', sa.String(), nullable=False),
        sa.Column('assignments', sa.JSON(), nullable=False),
        sa.Column('review_status', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False))
    for name in ('evidence_id', 'source_id', 'model', 'review_status'):
        op.create_index('ix_rag_chunks_' + name, 'rag_chunks', [name])
    op.create_table('rag_runs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('prompt_version', sa.String(), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=False),
        sa.Column('output', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False))
    op.execute("CREATE VIRTUAL TABLE rag_fts USING fts5(chunk_id UNINDEXED, text, tokenize='unicode61')")
    for operation in ('UPDATE', 'DELETE'):
        op.execute(f"CREATE TRIGGER immutable_rag_runs_{operation.lower()} BEFORE {operation} ON rag_runs BEGIN SELECT RAISE(ABORT, 'append-only record'); END")


def downgrade():
    op.execute('DROP TABLE rag_fts')
    op.drop_table('rag_runs')
    op.drop_table('rag_chunks')
