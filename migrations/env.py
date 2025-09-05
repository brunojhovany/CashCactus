from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig
import os

# Intentar usar la app Flask si está disponible; de lo contrario crearla manualmente.
flask_app = None
metadata = None
engine = None

def _bootstrap_flask():
    global flask_app, metadata, engine
    if flask_app:
        return
    try:
        from app import create_app, db  # type: ignore
        # Permitir usar DATABASE_URL / SQLALCHEMY_DATABASE_URI
        if os.environ.get('DATABASE_URL') and not os.environ.get('SQLALCHEMY_DATABASE_URI'):
            os.environ['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
        # SECRET_KEY mínimo para inicializar
        os.environ.setdefault('SECRET_KEY', 'alembic-temp-key')
        flask_app = create_app()
        with flask_app.app_context():
            metadata = db.metadata
            engine = db.engine
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"No se pudo inicializar la app Flask para migraciones: {e}")

def get_engine():
    if engine is None:
        _bootstrap_flask()
    return engine

def get_metadata():
    if metadata is None:
        _bootstrap_flask()
    return metadata

def run_migrations_offline() -> None:
    eng = get_engine()
    url = str(eng.url)
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()