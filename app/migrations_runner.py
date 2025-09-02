import os
from contextlib import suppress
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from flask import current_app

DEFAULT_LOCK_ID = 815551  # Cambiable vía MIGRATIONS_ADVISORY_LOCK_ID

def _alembic_config(sqlalchemy_url: str) -> Config:
    """Construir Config de Alembic asegurando script_location.

    Busca primero migrations/alembic.ini (estructura habitual) y si no existe,
    intenta fallback a alembic.ini en raíz. Ajusta script_location explícitamente
    para evitar errores como: "No 'script_location' key found in configuration".
    """
    project_root = Path(__file__).resolve().parents[1]
    mig_dir = project_root / "migrations"
    # Ruta esperada principal
    primary_cfg = mig_dir / "alembic.ini"
    fallback_cfg = project_root / "alembic.ini"
    if primary_cfg.exists():
        cfg_path = primary_cfg
    elif fallback_cfg.exists():
        cfg_path = fallback_cfg
    else:
        raise RuntimeError(
            "No se encontró alembic.ini (buscado en migrations/ y raíz). Asegura que el directorio de migraciones está presente."
        )
    cfg = Config(str(cfg_path))
    # Garantizar script_location coherente (cuando el ini vive dentro de migrations/ ya es '.').
    # Si el archivo está fuera, apuntar explícitamente al directorio migrations.
    if not cfg.get_main_option("script_location"):
        cfg.set_main_option("script_location", str(mig_dir))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)
    return cfg

def _acquire_lock(engine) -> bool:
    if engine.dialect.name != "postgresql":
        return True
    lock_id = int(os.getenv("MIGRATIONS_ADVISORY_LOCK_ID", DEFAULT_LOCK_ID))
    with engine.begin() as conn:
        row = conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).fetchone()
        return bool(row[0])

def _release_lock(engine):
    if engine.dialect.name != "postgresql":
        return
    lock_id = int(os.getenv("MIGRATIONS_ADVISORY_LOCK_ID", DEFAULT_LOCK_ID))
    with suppress(Exception):
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})

def run_automigrations():
    app = current_app
    if not os.getenv("AUTO_MIGRATE"):
        app.logger.info("[migrations] AUTO_MIGRATE desactivado")
        return
    ext = app.extensions.get("sqlalchemy")
    engine = getattr(ext, "db").engine if ext else None
    if engine is None:
        app.logger.warning("[migrations] No se encontró engine SQLAlchemy")
        return
    if not _acquire_lock(engine):
        app.logger.info("[migrations] Otro proceso posee el lock; omitiendo")
        return
    try:
        app.logger.info("[migrations] alembic upgrade head")
        cfg = _alembic_config(str(engine.url))
        command.upgrade(cfg, "head")
        app.logger.info("[migrations] OK")
    except Exception as exc:
        app.logger.exception("[migrations] Error: %s", exc)
        if os.getenv("MIGRATIONS_FAIL_FAST", "1") == "1":
            raise
    finally:
        _release_lock(engine)

def init_auto_migration(app):
    with app.app_context():
        run_automigrations()
