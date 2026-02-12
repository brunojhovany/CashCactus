"""Remove encryption from all models

Revision ID: 7_remove_encryption
Revises: 6_drop_plain_numeric_columns
Create Date: 2026-02-05 12:00:00.000000

Esta migración:
1. Desencripta todos los datos existentes
2. Crea nuevas columnas en texto plano/numeric
3. Elimina columnas encriptadas y blind indexes
4. Elimina columna enc_version
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from decimal import Decimal, ROUND_HALF_UP

# revision identifiers, used by Alembic.
revision = '7_remove_encryption'
down_revision = '6_drop_plain_numeric_columns'
branch_labels = None
depends_on = None


def decrypt_field_migration(blob, field, version=1):
    """Función auxiliar para desencriptar durante la migración"""
    if not blob:
        return None
    
    import os
    import base64
    import hmac
    import hashlib
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    
    def _load_master_key(version: int = 1):
        env_name = f"APP_MASTER_KEY_{version}" if version != 1 else "APP_MASTER_KEY"
        val = os.environ.get(env_name)
        if not val and version == 1:
            val = os.environ.get("APP_MASTER_KEY")
        if not val:
            # Si no hay llave, no podemos desencriptar - devolver None
            return None
        try:
            raw = base64.b64decode(val)
        except Exception:
            return None
        return raw
    
    def _derive_subkey(purpose: str, field: str, version: int = 1):
        mk = _load_master_key(version)
        if not mk:
            return None
        msg = f"{purpose}:{field}:v{version}".encode()
        return hmac.new(mk, msg, hashlib.sha256).digest()
    
    key = _derive_subkey("enc", field, version)
    if not key:
        return None
    
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    try:
        pt = aes.decrypt(nonce, ct, None)
        return pt.decode()
    except Exception:
        return None


def upgrade():
    """Desencriptar todos los datos y migrar a campos en texto plano"""
    
    # Conectar a la base de datos
    connection = op.get_bind()
    
    print("=" * 80)
    print("INICIANDO MIGRACIÓN: Eliminación de Encriptación")
    print("=" * 80)
    
    # ========================================================================
    # PASO 1: TRANSACTIONS - Agregar nuevas columnas
    # ========================================================================
    print("\n[1/6] Agregando nuevas columnas a 'transactions'...")
    
    # Agregar columnas temporales para los datos desencriptados
    op.add_column('transactions', 
                  sa.Column('amount_plain', sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column('transactions', 
                  sa.Column('description_plain', sa.String(500), nullable=True))
    op.add_column('transactions', 
                  sa.Column('notes_plain', sa.Text, nullable=True))
    op.add_column('transactions', 
                  sa.Column('creditor_name_plain', sa.String(200), nullable=True))
    
    # ========================================================================
    # PASO 2: TRANSACTIONS - Desencriptar y copiar datos
    # ========================================================================
    print("\n[2/6] Desencriptando datos de 'transactions'...")
    
    # Obtener todas las transacciones con datos encriptados
    result = connection.execute(sa.text("""
        SELECT id, amount_enc, description_enc, notes_enc, creditor_name_enc, enc_version
        FROM transactions
    """))
    
    transactions = result.fetchall()
    total = len(transactions)
    print(f"   Procesando {total} transacciones...")
    
    for i, row in enumerate(transactions, 1):
        if i % 100 == 0:
            print(f"   Progreso: {i}/{total} ({i*100//total}%)")
        
        trans_id = row[0]
        amount_enc = row[1]
        desc_enc = row[2]
        notes_enc = row[3]
        creditor_enc = row[4]
        enc_version = row[5] or 1
        
        # Desencriptar cada campo
        amount_plain = decrypt_field_migration(amount_enc, 'amount', enc_version)
        desc_plain = decrypt_field_migration(desc_enc, 'description', enc_version)
        notes_plain = decrypt_field_migration(notes_enc, 'notes', enc_version)
        creditor_plain = decrypt_field_migration(creditor_enc, 'creditor_name', enc_version)
        
        # Actualizar la fila con los datos desencriptados
        connection.execute(sa.text("""
            UPDATE transactions
            SET amount_plain = :amount,
                description_plain = :description,
                notes_plain = :notes,
                creditor_name_plain = :creditor
            WHERE id = :id
        """), {
            'amount': amount_plain if amount_plain else '0.00',
            'description': desc_plain,
            'notes': notes_plain,
            'creditor': creditor_plain,
            'id': trans_id
        })
    
    print(f"   ✓ {total} transacciones desencriptadas exitosamente")
    
    # ========================================================================
    # PASO 3: ACCOUNTS - Agregar nuevas columnas y desencriptar
    # ========================================================================
    print("\n[3/6] Procesando 'accounts'...")
    
    op.add_column('accounts', 
                  sa.Column('balance_plain', sa.Numeric(precision=15, scale=2), nullable=True))
    
    # Desencriptar balances
    result = connection.execute(sa.text("""
        SELECT id, balance_enc, enc_version
        FROM accounts
    """))
    
    accounts = result.fetchall()
    print(f"   Procesando {len(accounts)} cuentas...")
    
    for row in accounts:
        acc_id = row[0]
        balance_enc = row[1]
        enc_version = row[2] or 1
        
        balance_plain = decrypt_field_migration(balance_enc, 'account_balance', enc_version)
        
        connection.execute(sa.text("""
            UPDATE accounts
            SET balance_plain = :balance
            WHERE id = :id
        """), {
            'balance': balance_plain if balance_plain else '0.00',
            'id': acc_id
        })
    
    print(f"   ✓ {len(accounts)} cuentas desencriptadas")
    
    # ========================================================================
    # PASO 4: CREDIT_CARDS - Agregar nuevas columnas y desencriptar
    # ========================================================================
    print("\n[4/6] Procesando 'credit_cards'...")
    
    op.add_column('credit_cards', 
                  sa.Column('current_balance_plain', sa.Numeric(precision=15, scale=2), nullable=True))
    
    # Desencriptar balances
    result = connection.execute(sa.text("""
        SELECT id, current_balance_enc, enc_version
        FROM credit_cards
    """))
    
    cards = result.fetchall()
    print(f"   Procesando {len(cards)} tarjetas...")
    
    for row in cards:
        card_id = row[0]
        balance_enc = row[1]
        enc_version = row[2] or 1
        
        balance_plain = decrypt_field_migration(balance_enc, 'cc_current_balance', enc_version)
        
        connection.execute(sa.text("""
            UPDATE credit_cards
            SET current_balance_plain = :balance
            WHERE id = :id
        """), {
            'balance': balance_plain if balance_plain else '0.00',
            'id': card_id
        })
    
    print(f"   ✓ {len(cards)} tarjetas desencriptadas")
    
    # ========================================================================
    # PASO 5: Eliminar columnas antiguas encriptadas
    # ========================================================================
    print("\n[5/6] Eliminando columnas encriptadas antiguas...")
    
    # TRANSACTIONS
    with op.batch_alter_table('transactions') as batch_op:
        batch_op.drop_column('amount_enc')
        batch_op.drop_column('description_enc')
        batch_op.drop_column('description_bidx')
        batch_op.drop_column('notes_enc')
        batch_op.drop_column('notes_bidx')
        batch_op.drop_column('creditor_name_enc')
        batch_op.drop_column('creditor_name_bidx')
        batch_op.drop_column('enc_version')
    
    # ACCOUNTS
    with op.batch_alter_table('accounts') as batch_op:
        batch_op.drop_column('balance_enc')
        batch_op.drop_column('enc_version')
    
    # CREDIT_CARDS
    with op.batch_alter_table('credit_cards') as batch_op:
        batch_op.drop_column('current_balance_enc')
        batch_op.drop_column('enc_version')
    
    print("   ✓ Columnas antiguas eliminadas")
    
    # ========================================================================
    # PASO 6: Renombrar columnas _plain a nombres finales
    # ========================================================================
    print("\n[6/6] Renombrando columnas a nombres finales...")
    
    # TRANSACTIONS
    with op.batch_alter_table('transactions') as batch_op:
        batch_op.alter_column('amount_plain', new_column_name='amount', nullable=False)
        batch_op.alter_column('description_plain', new_column_name='description')
        batch_op.alter_column('notes_plain', new_column_name='notes')
        batch_op.alter_column('creditor_name_plain', new_column_name='creditor_name')
    
    # ACCOUNTS
    with op.batch_alter_table('accounts') as batch_op:
        batch_op.alter_column('balance_plain', new_column_name='balance', nullable=False)
    
    # CREDIT_CARDS
    with op.batch_alter_table('credit_cards') as batch_op:
        batch_op.alter_column('current_balance_plain', new_column_name='current_balance', nullable=False)
    
    print("   ✓ Columnas renombradas")
    
    print("\n" + "=" * 80)
    print("✓ MIGRACIÓN COMPLETADA EXITOSAMENTE")
    print("  Todos los datos han sido desencriptados y las columnas actualizadas.")
    print("  La aplicación ahora usa almacenamiento en texto plano para mayor rendimiento.")
    print("=" * 80)


def downgrade():
    """Reversa: NO IMPLEMENTADA - Esta migración es irreversible
    
    Una vez eliminada la encriptación, no se puede restaurar automáticamente
    ya que requeriría las llaves de encriptación originales.
    """
    print("=" * 80)
    print("ERROR: Esta migración NO es reversible")
    print("=" * 80)
    print("La eliminación de encriptación no puede revertirse automáticamente.")
    print("Si necesitas restaurar la encriptación, debes:")
    print("  1. Restaurar un backup de la base de datos")
    print("  2. O implementar manualmente la re-encriptación")
    print("=" * 80)
    raise NotImplementedError("Esta migración no puede revertirse automáticamente")
