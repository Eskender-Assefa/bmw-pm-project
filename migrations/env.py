from alembic import context
from backend.models import Base
from backend.db import engine

def offline():
    context.configure(url=str(engine.url),target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction(): context.run_migrations()

def online():
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=True)
        with context.begin_transaction(): context.run_migrations()

offline() if context.is_offline_mode() else online()
