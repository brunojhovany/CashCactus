"""Herramienta auxiliar (opcional) para sincronización mínima del esquema.

Se movió fuera del core de la app para mantener la separación de responsabilidades.
Uso típico (solo entornos simples / desarrollo rápido):

    python -m migrations.auto_schema_sync [--dry-run] [--verbose]

Características (aditivas e idempotentes):
 - Crear tablas faltantes declaradas en los modelos
 - Agregar columnas simples (sin cambios de tipo ni drops)
 - Crear índices simples (Column(index=True))

Para entornos formales usar exclusivamente `alembic upgrade head`.
"""
from __future__ import annotations
import os, sys, argparse
from typing import List
from sqlalchemy import inspect, text

# Asegurar que el directorio raíz del proyecto esté en sys.path cuando se ejecuta
# este script desde dentro de 'migrations/'.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from app import create_app, db  # type: ignore
except ModuleNotFoundError as e:
    print("[schema-upgrade] ERROR: No se pudo importar 'app'. Ejecuta el script desde la raíz del proyecto o ajusta PYTHONPATH.")
    print(f"[schema-upgrade] sys.path actual: {sys.path}")
    raise

def log(msg: str):
    print(f"[auto-schema-sync] {msg}")


def debug(msg: str):
    if os.environ.get('VERBOSE') == '1':
        log(msg)


def sync(dry: bool) -> int:
    # Permitir override de DB URL
    if os.environ.get('DATABASE_URL') and not os.environ.get('SQLALCHEMY_DATABASE_URI'):
        os.environ['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']

    # SECRET_KEY temporal si falta
    os.environ.setdefault('SECRET_KEY', os.urandom(16).hex())

    app = create_app()
    actions: List[str] = []
    with app.app_context():
        engine = db.engine
        insp = inspect(engine)
        existing_tables = set(insp.get_table_names())

        # Registrar modelos
        from app.models.user import User  # noqa: F401
        from app.models.account import Account  # noqa: F401
        from app.models.transaction import Transaction  # noqa: F401
        from app.models.credit_card import CreditCard  # noqa: F401
        from app.models.reminder import Reminder  # noqa: F401

        metadata = db.metadata

        # 1. Tablas faltantes
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                actions.append(f"CREATE TABLE {table.name}")
                if not dry:
                    debug(f"Creating table {table.name}")
                    table.create(bind=engine, checkfirst=True)

        # 2. Columnas faltantes
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {c['name'] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                coltype = col.type.compile(engine.dialect)
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}"  # sin NOT NULL para evitar fallos
                actions.append(ddl)
                if not dry:
                    debug(f"Adding column {table.name}.{col.name}")
                    try:
                        with engine.begin() as conn:
                            conn.execute(text(ddl))
                    except Exception as e:  # pragma: no cover
                        log(f"WARN: no se pudo agregar columna {table.name}.{col.name}: {e}")

        # 3. Índices simples
        for table in metadata.sorted_tables:
            try:
                idx_existing = {ix['name'] for ix in insp.get_indexes(table.name)}
            except Exception:  # pragma: no cover
                continue
            for col in table.columns:
                if getattr(col, 'index', False):
                    idx_name = f"ix_{table.name}_{col.name}"
                    if idx_name not in idx_existing:
                        actions.append(f"CREATE INDEX {idx_name} ON {table.name} ({col.name})")
                        if not dry:
                            debug(f"Creating index {idx_name}")
                            try:
                                with engine.begin() as conn:
                                    conn.execute(text(f"CREATE INDEX {idx_name} ON {table.name} ({col.name})"))
                            except Exception as e:  # pragma: no cover
                                log(f"WARN: no se pudo crear índice {idx_name}: {e}")

    if not actions:
        log("Sin cambios: esquema actualizado")
    else:
        log("Acciones planeadas (ejecutadas salvo --dry-run):")
        for a in actions:
            log(f"  - {a}")
        if dry:
            log("Modo dry-run: no se aplicaron cambios")
        else:
            log("Sincronización terminada")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sincronización mínima de esquema (aditiva)")
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)
    if args.verbose:
        os.environ['VERBOSE'] = '1'
    return sync(dry=args.dry_run)


if __name__ == '__main__':  # pragma: no cover
    try:
        sys.exit(main())
    except Exception as exc:  # pylint: disable=broad-except
        log(f"ERROR: {exc}")
        sys.exit(1)
