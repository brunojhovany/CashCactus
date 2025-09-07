"""Migrar datos legacy de columnas en claro (description, notes, creditor_name)
 a columnas cifradas *_enc + *_bidx en tabla transactions.

Uso:
  APP_MASTER_KEY=... FLASK_APP=run.py python -m scripts.migrate_legacy_transaction_plaintext \
      --batch-size 500 --null-after

Argumentos:
  --batch-size N    Número de filas por lote (default 500)
  --null-after      Coloca a NULL las columnas en claro tras cifrar (no las elimina)
  --dry-run         No escribe cambios, sólo muestra conteos

Lógica:
  - Detecta si existen columnas plaintext.
  - Selecciona filas donde haya plaintext y el cifrado correspondiente esté vacío.
  - Cifra campo por campo y actualiza enc_version (usa APP_ENC_ACTIVE_VERSION o 1).

Seguro reentrante: puede ejecutarse varias veces; sólo procesa filas pendientes.
"""
from __future__ import annotations

import argparse
from typing import List, Dict, Any
from sqlalchemy import text
from app import create_app, db
from app.utils.crypto_fields import encrypt_field, blind_index, get_active_enc_version

PLAINTEXT_COLS = ["description", "notes", "creditor_name"]
ENC_MAP = {
    "description": ("description_enc", "description_bidx"),
    "notes": ("notes_enc", "notes_bidx"),
    "creditor_name": ("creditor_name_enc", "creditor_name_bidx"),
}


def detect_plaintext_cols() -> List[str]:
    insp = db.inspect(db.engine)
    cols = {c["name"] for c in insp.get_columns("transactions")}
    return [c for c in PLAINTEXT_COLS if c in cols]


def fetch_batch(plain_cols: List[str], batch_size: int) -> List[Dict[str, Any]]:
    # Construir condiciones dinámicas
    cond_plain = " OR ".join([f"{c} IS NOT NULL" for c in plain_cols])
    cond_enc_parts = []
    for p in plain_cols:
        enc_col, _ = ENC_MAP[p]
        cond_enc_parts.append(f"{enc_col} IS NULL")
    cond_enc = " OR ".join(cond_enc_parts)
    sql = f"""
        SELECT id, enc_version, {', '.join(plain_cols)}
        FROM transactions
        WHERE ({cond_plain}) AND ({cond_enc})
        ORDER BY id ASC
        LIMIT :batch
    """
    rows = db.session.execute(text(sql), {"batch": batch_size}).mappings().all()
    return [dict(r) for r in rows]


def process_rows(rows: List[Dict[str, Any]], plain_cols: List[str], null_after: bool, dry_run: bool) -> int:
    if not rows:
        return 0
    active_version = get_active_enc_version()
    total = 0
    for r in rows:
        sets = []
        params = {"id": r["id"]}
        enc_version = r.get("enc_version") or active_version
        if r.get("enc_version") != enc_version:
            sets.append("enc_version = :enc_version")
            params["enc_version"] = enc_version
        for p in plain_cols:
            val = r.get(p)
            if val is None:
                continue
            enc_col, bidx_col = ENC_MAP[p]
            # Evitar recalcular si ya tiene algo (consultamos null en fetch, pero por seguridad)
            sets.append(f"{enc_col} = :{enc_col}")
            sets.append(f"{bidx_col} = :{bidx_col}")
            params[enc_col] = encrypt_field(val, p, enc_version)
            params[bidx_col] = blind_index(val, p, enc_version)
            if null_after:
                sets.append(f"{p} = NULL")
        if not sets:
            continue
        sql_update = f"UPDATE transactions SET {', '.join(sets)} WHERE id = :id"
        if not dry_run:
            db.session.execute(text(sql_update), params)
        total += 1
    if not dry_run:
        db.session.commit()
    return total


def migrate(batch_size: int, null_after: bool, dry_run: bool):
    plain_cols = detect_plaintext_cols()
    if not plain_cols:
        print("[migrate] No hay columnas plaintext presentes. Nada que hacer.")
        return
    print(f"[migrate] Columnas plaintext detectadas: {plain_cols}")
    migrated_total = 0
    while True:
        batch = fetch_batch(plain_cols, batch_size)
        if not batch:
            break
        migrated = process_rows(batch, plain_cols, null_after, dry_run)
        migrated_total += migrated
        print(f"[migrate] Lote procesado: {migrated} filas (acumulado {migrated_total})")
        if migrated == 0:
            break
    print(f"[migrate] FIN. Filas migradas: {migrated_total}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--null-after", action="store_true", help="Poner a NULL las columnas plaintext luego de cifrar")
    parser.add_argument("--dry-run", action="store_true", help="No escribir cambios")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        migrate(args.batch_size, args.null_after, args.dry_run)


if __name__ == "__main__":  # pragma: no cover
    main()
