from __future__ import annotations

import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Import the SQLAlchemy models Base and engine from the app
from backend.database import Base, engine  # type: ignore

config = context.config
fileConfig(config.config_file_name)

# Use the metadata from the project's declarative base
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

def run_migrations_offline():
    import os
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        url = config.get_main_option("sqlalchemy.url", raw=True)
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
