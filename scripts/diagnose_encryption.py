#!/usr/bin/env python3
"""
Script de diagnóstico para problemas de cifrado.
Verifica el estado de los campos cifrados y detecta problemas comunes.
"""
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.transaction import Transaction
from app.models.credit_card import CreditCard
from app.models.account import Account
from app.utils.crypto_fields import decrypt_field, get_active_enc_version
from sqlalchemy import inspect

def diagnose_encryption():
    """Diagnosticar problemas de cifrado en la base de datos."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("DIAGNÓSTICO DE CIFRADO")
        print("=" * 80)
        print()
        
        # Verificar configuración de claves
        print("1. CONFIGURACIÓN DE CLAVES")
        print("-" * 80)
        master_key = os.environ.get('APP_MASTER_KEY')
        active_version = get_active_enc_version()
        
        if not master_key:
            print("⚠️  WARNING: APP_MASTER_KEY no está configurada!")
            print("   Se está usando una clave efímera que cambia con cada reinicio.")
            print("   Esto causa que los datos cifrados no se puedan desencriptar.")
            print()
            print("   SOLUCIÓN: Exporta APP_MASTER_KEY antes de iniciar la app:")
            print("   export APP_MASTER_KEY=$(python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())')")
            print()
        else:
            print(f"✓ APP_MASTER_KEY está configurada (primeros 8 chars: {master_key[:8]}...)")
        
        print(f"✓ Versión activa de cifrado: {active_version}")
        print()
        
        # Diagnosticar tarjetas de crédito
        print("2. TARJETAS DE CRÉDITO")
        print("-" * 80)
        cards = CreditCard.query.all()
        
        if not cards:
            print("   No hay tarjetas de crédito en la base de datos.")
        else:
            problematic_cards = []
            for card in cards:
                print(f"\n   Tarjeta ID {card.id}: {card.name}")
                
                # Verificar campo cifrado
                if not card.current_balance_enc:
                    print(f"   ⚠️  current_balance_enc está NULL/vacío")
                    problematic_cards.append(card)
                else:
                    print(f"   ✓ current_balance_enc existe ({len(card.current_balance_enc)} bytes)")
                
                # Verificar versión
                if not card.enc_version:
                    print(f"   ⚠️  enc_version está NULL")
                    problematic_cards.append(card)
                else:
                    print(f"   ✓ enc_version: {card.enc_version}")
                
                # Intentar desencriptar
                try:
                    balance = card.current_balance
                    print(f"   ✓ Desencriptación exitosa: ${balance:.2f}")
                    
                    # Verificar contra transacciones
                    transactions = Transaction.query.filter_by(credit_card_id=card.id).all()
                    calc_balance = 0.0
                    for t in transactions:
                        if t.transaction_type == 'expense':
                            calc_balance += t.amount
                        elif t.transaction_type == 'income':
                            calc_balance -= t.amount
                    calc_balance = max(0.0, calc_balance)
                    
                    print(f"   📊 Balance calculado desde transacciones: ${calc_balance:.2f}")
                    print(f"   📊 Número de transacciones: {len(transactions)}")
                    
                    if abs(balance - calc_balance) > 0.01:
                        print(f"   ⚠️  DISCREPANCIA: Diferencia de ${abs(balance - calc_balance):.2f}")
                        problematic_cards.append(card)
                    
                except Exception as e:
                    print(f"   ❌ Error al desencriptar: {e}")
                    problematic_cards.append(card)
            
            if problematic_cards:
                print(f"\n   ⚠️  {len(problematic_cards)} tarjeta(s) con problemas detectadas")
            else:
                print("\n   ✓ Todas las tarjetas están OK")
        
        print()
        
        # Diagnosticar cuentas
        print("3. CUENTAS BANCARIAS")
        print("-" * 80)
        accounts = Account.query.all()
        
        if not accounts:
            print("   No hay cuentas en la base de datos.")
        else:
            problematic_accounts = []
            for account in accounts:
                print(f"\n   Cuenta ID {account.id}: {account.name}")
                
                # Verificar campo cifrado
                if not account.balance_enc:
                    print(f"   ⚠️  balance_enc está NULL/vacío")
                    problematic_accounts.append(account)
                else:
                    print(f"   ✓ balance_enc existe ({len(account.balance_enc)} bytes)")
                
                # Verificar versión
                if not account.enc_version:
                    print(f"   ⚠️  enc_version está NULL")
                    problematic_accounts.append(account)
                else:
                    print(f"   ✓ enc_version: {account.enc_version}")
                
                # Intentar desencriptar
                try:
                    balance = account.balance
                    print(f"   ✓ Desencriptación exitosa: ${balance:.2f}")
                except Exception as e:
                    print(f"   ❌ Error al desencriptar: {e}")
                    problematic_accounts.append(account)
            
            if problematic_accounts:
                print(f"\n   ⚠️  {len(problematic_accounts)} cuenta(s) con problemas detectadas")
            else:
                print("\n   ✓ Todas las cuentas están OK")
        
        print()
        
        # Diagnosticar transacciones
        print("4. TRANSACCIONES (muestra de 10 más recientes)")
        print("-" * 80)
        transactions = Transaction.query.order_by(Transaction.date.desc()).limit(10).all()
        
        if not transactions:
            print("   No hay transacciones en la base de datos.")
        else:
            problematic_txs = []
            for tx in transactions:
                print(f"\n   Transacción ID {tx.id}")
                
                # Verificar amount_enc
                if not tx.amount_enc:
                    print(f"   ⚠️  amount_enc está NULL/vacío")
                    problematic_txs.append(tx)
                else:
                    try:
                        amount = tx.amount
                        print(f"   ✓ amount: ${amount:.2f}")
                    except Exception as e:
                        print(f"   ❌ Error al desencriptar amount: {e}")
                        problematic_txs.append(tx)
                
                # Verificar description_enc
                if tx.description_enc:
                    try:
                        desc = tx.description
                        print(f"   ✓ description: {desc[:50]}...")
                    except Exception as e:
                        print(f"   ⚠️  Error al desencriptar description: {e}")
                else:
                    print(f"   ℹ️  description_enc está vacío")
                
                # Verificar versión
                if not tx.enc_version:
                    print(f"   ⚠️  enc_version está NULL")
                else:
                    print(f"   ✓ enc_version: {tx.enc_version}")
            
            if problematic_txs:
                print(f"\n   ⚠️  {len(problematic_txs)} transacción(es) con problemas detectadas")
            else:
                print("\n   ✓ Todas las transacciones muestreadas están OK")
        
        print()
        print("=" * 80)
        print("RESUMEN")
        print("=" * 80)
        
        if not master_key:
            print("\n🔴 PROBLEMA CRÍTICO DETECTADO:")
            print("   APP_MASTER_KEY no está configurada. Los datos cifrados no se pueden")
            print("   desencriptar correctamente y aparecen como ceros.")
            print("\n📝 SOLUCIÓN:")
            print("   1. Genera una clave maestra:")
            print("      python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'")
            print("\n   2. Exporta la clave antes de iniciar la app:")
            print("      export APP_MASTER_KEY='<tu-clave-generada>'")
            print("\n   3. Para persistencia, agrégala a tu .env o configuración del servidor:")
            print("      echo 'export APP_MASTER_KEY=\"<tu-clave>\"' >> ~/.bashrc")
            print("\n   4. Ejecuta el script de re-cifrado:")
            print("      python scripts/recrypt_all_data.py")
        else:
            print("\n✓ La configuración de cifrado parece estar correcta.")
            print("  Si aún ves problemas, ejecuta:")
            print("  python scripts/recrypt_all_data.py")
        
        print()

if __name__ == '__main__':
    diagnose_encryption()
