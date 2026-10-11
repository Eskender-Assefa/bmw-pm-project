from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from .config import DB_URL, DATA_DIR, ensure_directories
from .models import Base

ensure_directories()
engine = create_engine(DB_URL, connect_args={'check_same_thread': False, 'timeout': 30})

@event.listens_for(engine, 'connect')
def sqlite_settings(connection, _):
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA busy_timeout=30000')

SessionLocal = sessionmaker(engine, expire_on_commit=False)

def session_dependency():
    with SessionLocal() as session:
        yield session

def create_search_index(connection):
    connection.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(evidence_id UNINDEXED, text, tokenize='unicode61')"))

def install_guards(connection):
    for table in ('audit_events', 'requirement_revisions', 'priority_runs', 'decisions', 'analysis_runs', 'exports'):
        for operation in ('UPDATE', 'DELETE'):
            connection.execute(text(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only record'); END"))

def initialize_test_database():
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        create_search_index(c)
        install_guards(c)
