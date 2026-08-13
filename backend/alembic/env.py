"""Alembic environment configuration for Basir AI.

Reads DATABASE_URL from the environment (via python-dotenv) and wires in the
app's declarative Base so autogenerate can detect schema changes.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Bootstrap: load env vars and import Base + all models before anything else
# ---------------------------------------------------------------------------
from dotenv import load_dotenv  # noqa: E402 (after stdlib imports)

load_dotenv()

# Import Base and all ORM models so autogenerate can see them.
from app.database import Base, DATABASE_URL  # noqa: E402
import app.models  # noqa: F401, E402  registers all table metadata

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------
config = context.config

# Inject the runtime DATABASE_URL so Alembic doesn't rely on alembic.ini value.
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live PostgreSQL instance."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
