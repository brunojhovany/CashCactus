#!/usr/bin/env python3
"""
Script para re-cifrar todos los datos cuando la clave maestra cambió.
USAR CON PRECAUCIÓN: Este script recalcula y re-cifra todos los saldos.
"""
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.transaction import Transaction
from app.models.credit_card import CreditCard
from app.models.account import Account
from app.utils.crypto_fields import get_active_enc_version

def recrypt_all_data():
    """Re-cifrar todos los datos con la clave maestra actual."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("RE-CIFRADO DE DATOS")
        print("=" * 80)
        print()
        
        # Verificar que hay clave configurada
        master_key = os.environ.get('APP_MASTER_KEY')
        if not master_key:
            print("❌ ERROR: APP_MASTER_KEY no está configurada.")
            print("   Debes exportar una clave maestra antes de ejecutar este script.")
            print()
            print("   Genera una clave:")
            print("   python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'")
            print()
            print("   Luego exporta:")
            print("   export APP_MASTER_KEY='<tu-clave-generada>'")
            sys.exit(1)
        
        active_version = get_active_enc_version()
        print(f"✓ Usando APP_MASTER_KEY (primeros 8 chars: {master_key[:8]}...)")
        print(f"✓ Versión de cifrado: {active_version}")
        print()
        
        # Confirmar
        print("⚠️  ADVERTENCIA: Este script recalculará y re-cifrará todos los saldos.")
        print("   Asegúrate de tener un backup de la base de datos.")
        print()
        response = input("¿Deseas continuar? (escribe 'SI' para confirmar): ")
        if response != 'SI':
            print("Operación cancelada.")
            sys.exit(0)
        
        print()
        print("Iniciando re-cifrado...")
        print()
        
        # Re-cifrar tarjetas de crédito
        print("1. RE-CIFRANDO TARJETAS DE CRÉDITO")
        print("-" * 80)
        cards = CreditCard.query.all()
        
        for card in cards:
            print(f"   Procesando tarjeta {card.id}: {card.name}")
            
            try:
                # Recalcular balance desde transacciones
                transactions = Transaction.query.filter_by(credit_card_id=card.id).all()
                calculated_balance = 0.0
                
                for t in transactions:
                    if t.transaction_type == 'expense':
                        calculated_balance += t.amount
                    elif t.transaction_type == 'income':
                        calculated_balance -= t.amount
                
                calculated_balance = max(0.0, calculated_balance)
                
                # Actualizar (esto fuerza re-cifrado con clave actual)
                old_balance = card.current_balance if card.current_balance_enc else 0.0
                card.current_balance = calculated_balance
                card.enc_version = active_version
                card.update_minimum_payment()
                
                print(f"      Balance anterior: ${old_balance:.2f}")
                print(f"      Balance recalculado: ${calculated_balance:.2f}")
                print(f"      ✓ Re-cifrado exitoso")
                
            except Exception as e:
                print(f"      ❌ Error: {e}")
        
        db.session.commit()
        print(f"\n   ✓ {len(cards)} tarjeta(s) procesada(s)")
        print()
        
        # Re-cifrar cuentas
        print("2. RE-CIFRANDO CUENTAS BANCARIAS")
        print("-" * 80)
        accounts = Account.query.all()
        
        for account in accounts:
            print(f"   Procesando cuenta {account.id}: {account.name}")
            
            try:
                # Recalcular balance desde transacciones
                old_balance = account.balance if account.balance_enc else 0.0
                new_balance = account.update_balance()
                account.enc_version = active_version
                
                print(f"      Balance anterior: ${old_balance:.2f}")
                print(f"      Balance recalculado: ${new_balance:.2f}")
                print(f"      ✓ Re-cifrado exitoso")
                
            except Exception as e:
                print(f"      ❌ Error: {e}")
        
        db.session.commit()
        print(f"\n   ✓ {len(accounts)} cuenta(s) procesada(s)")
        print()
        
        # Re-cifrar transacciones
        print("3. RE-CIFRANDO TRANSACCIONES")
        print("-" * 80)
        transactions = Transaction.query.all()
        
        processed = 0
        errors = 0
        
        for tx in transactions:
            try:
                # Leer valores actuales (fuerza desencriptación)
                amount = tx.amount
                desc = tx.description
                notes = tx.notes
                creditor = tx.creditor_name
                
                # Escribirlos de vuelta (fuerza re-cifrado con clave actual)
                tx.amount = amount
                if desc:
                    tx.description = desc
                if notes:
                    tx.notes = notes
                if creditor:
                    tx.creditor_name = creditor
                tx.enc_version = active_version
                
                processed += 1
                
                if processed % 100 == 0:
                    print(f"      Procesadas {processed} transacciones...")
                    db.session.commit()
                
            except Exception as e:
                print(f"      ⚠️  Error en transacción {tx.id}: {e}")
                errors += 1
        
        db.session.commit()
        print(f"\n   ✓ {processed} transacción(es) procesada(s)")
        if errors > 0:
            print(f"   ⚠️  {errors} error(es) encontrado(s)")
        print()
        
        print("=" * 80)
        print("RE-CIFRADO COMPLETADO")
        print("=" * 80)
        print()
        print("✓ Todos los datos han sido re-cifrados con la clave maestra actual.")
        print("  Reinicia la aplicación y verifica que los datos se muestran correctamente.")
        print()

if __name__ == '__main__':
    recrypt_all_data()
