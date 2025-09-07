"""Script de rotación de llaves para campos cifrados de Transaction.

Uso (ejemplo):
    APP_MASTER_KEY_1=... APP_MASTER_KEY_2=... FLASK_APP=run.py \
    python -m scripts.rotate_transaction_keys --from-version 1 --to-version 2 --batch-size 200

Flujo:
 1. Lee filas con enc_version == from_version.
 2. Descifra campos (description, notes, creditor_name) con llave old.
 3. Re-cifra con nueva versión (to_version) y actualiza enc_version.
 4. Commit por lotes para limitar locks/memoria.

Seguridad: ejecutar con base de datos en backup reciente. Idempotente: si falla
puede reanudarse (filtra por enc_version).
"""
from __future__ import annotations

import argparse
import os
from flask import current_app
from app import create_app, db
from app.models.transaction import Transaction
from app.utils.crypto_fields import encrypt_field, blind_index, decrypt_field


def rotate_batch(from_version: int, to_version: int, batch_size: int) -> int:
    q = (
        Transaction.query.filter(Transaction.enc_version == from_version)
        .order_by(Transaction.id.asc())
        .limit(batch_size)
    )
    rows = q.all()
    changed = 0
    for t in rows:
        # Descifrar con old version
        desc = decrypt_field(t.description_enc, 'description', from_version)
        notes = decrypt_field(t.notes_enc, 'notes', from_version)
        cred = decrypt_field(t.creditor_name_enc, 'creditor_name', from_version)
        # Re-cifrar con new version
        t.enc_version = to_version
        if desc is not None:
            t.description_enc = encrypt_field(desc, 'description', to_version)
            t.description_bidx = blind_index(desc, 'description', to_version)
        if notes is not None:
            t.notes_enc = encrypt_field(notes, 'notes', to_version)
            t.notes_bidx = blind_index(notes, 'notes', to_version)
        if cred is not None:
            t.creditor_name_enc = encrypt_field(cred, 'creditor_name', to_version)
            t.creditor_name_bidx = blind_index(cred, 'creditor_name', to_version)
        changed += 1
    if changed:
        db.session.commit()
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-version', type=int, required=True)
    parser.add_argument('--to-version', type=int, required=True)
    parser.add_argument('--batch-size', type=int, default=500)
    parser.add_argument('--max-batches', type=int, default=0, help='0 = ilimitado')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        total = 0
        batch_no = 0
        while True:
            if args.max_batches and batch_no >= args.max_batches:
                break
            changed = rotate_batch(args.from_version, args.to_version, args.batch_size)
            if not changed:
                break
            total += changed
            batch_no += 1
            print(f"[rotate] batch={batch_no} migrated={changed} total={total}")
        print(f"[rotate] DONE total migrated rows: {total}")


if __name__ == '__main__':  # pragma: no cover (script manual)
    main()
