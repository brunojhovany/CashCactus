#!/usr/bin/env python3
"""
Script rápido para verificar que la configuración está correcta.
"""
import os
import sys

print("=" * 80)
print("✅ VERIFICACIÓN RÁPIDA DE CONFIGURACIÓN")
print("=" * 80)
print()

# Check 1: APP_MASTER_KEY
master_key = os.environ.get('APP_MASTER_KEY')
if master_key:
    print("✅ APP_MASTER_KEY está configurada")
    print(f"   Primeros 8 caracteres: {master_key[:8]}...")
    print(f"   Longitud: {len(master_key)} caracteres")
    if len(master_key) < 40:
        print("   ⚠️  WARNING: La clave parece corta. Debería tener 44+ caracteres.")
else:
    print("❌ APP_MASTER_KEY NO está configurada")
    print("   Ejecuta: set -Ux APP_MASTER_KEY \"$(python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())')\"")
    sys.exit(1)

# Check 2: SECRET_KEY
secret_key = os.environ.get('SECRET_KEY')
if secret_key and secret_key != 'change-me':
    print("✅ SECRET_KEY está configurada")
elif secret_key == 'change-me':
    print("⚠️  SECRET_KEY usa valor por defecto inseguro")
    print("   Ejecuta: set -Ux SECRET_KEY \"$(python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())')\"")
else:
    print("❌ SECRET_KEY NO está configurada")

# Check 3: APP_ENC_ACTIVE_VERSION
enc_version = os.environ.get('APP_ENC_ACTIVE_VERSION', '1')
print(f"✅ APP_ENC_ACTIVE_VERSION: {enc_version}")

# Check 4: ALLOW_DEFAULT_SECRET (debe estar en 1 si SECRET_KEY es insegura)
allow_default = os.environ.get('ALLOW_DEFAULT_SECRET')
if secret_key == 'change-me' and allow_default != '1':
    print("⚠️  Necesitas: set -x ALLOW_DEFAULT_SECRET 1")

print()
print("=" * 80)
print("PRÓXIMOS PASOS:")
print("=" * 80)

if not master_key:
    print("1. Configura APP_MASTER_KEY (ver arriba)")
    print("2. Ejecuta: python scripts/recrypt_all_data.py")
    print("3. Reinicia la app")
else:
    print("✅ Configuración básica correcta!")
    print()
    print("Puedes:")
    print("1. Ejecutar diagnóstico completo:")
    print("   set -x ALLOW_DEFAULT_SECRET 1")
    print("   python scripts/diagnose_encryption.py")
    print()
    print("2. Si ves datos en 0, re-cifrar:")
    print("   set -x ALLOW_DEFAULT_SECRET 1")
    print("   python scripts/recrypt_all_data.py")
    print()
    print("3. Iniciar la app:")
    print("   python run.py")

print()
