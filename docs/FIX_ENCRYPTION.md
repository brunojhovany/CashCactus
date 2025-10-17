# 🔐 SOLUCIÓN: Datos aparecen como ceros

## ✅ Problema Identificado

El diagnóstico confirma que **APP_MASTER_KEY no está configurada**. Esto causa que:
- Los datos se cifren con una clave temporal que cambia cada vez que reinicias
- Al reiniciar, los datos antiguos no se pueden desencriptar
- Resultado: los campos cifrados aparecen como `0` o vacíos
- **Afecta a:** Saldos de tarjetas, balances de cuentas, balance general del dashboard, montos de transacciones

## 🚀 Solución Rápida (3 pasos)

### Paso 1: Generar una Clave Maestra

```fish
# Genera una clave segura de 32 bytes
python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'
```

**Ejemplo de salida:**
```
Xk9mL2YwNzRhOGQyMzE0ZTU2Nzg5MGFiY2RlZjEyMzQ=
```

⚠️ **IMPORTANTE:** Guarda esta clave en un lugar seguro. La necesitarás siempre.

### Paso 2: Configurar la Clave Permanentemente

Elige **UNA** de estas opciones según cómo ejecutas la app:

#### Opción A: Fish Shell (recomendado para tu entorno)

```fish
# Configurar para siempre
set -Ux APP_MASTER_KEY "TU-CLAVE-AQUI"
set -Ux APP_ENC_ACTIVE_VERSION 1
set -Ux SECRET_KEY "otra-clave-diferente-para-sesiones"

# Verificar que se guardó
echo $APP_MASTER_KEY
```

#### Opción B: Archivo .env (alternativa)

Crea/edita `.env` en la raíz del proyecto:

```bash
APP_MASTER_KEY=TU-CLAVE-AQUI
APP_ENC_ACTIVE_VERSION=1
SECRET_KEY=otra-clave-diferente-para-sesiones
```

Luego antes de iniciar:
```fish
export (cat .env | xargs)
```

### Paso 3: Re-cifrar los Datos Existentes

```fish
# Primero, haz un backup (por si acaso)
cp instance/finanzas.db instance/finanzas.db.backup

# Re-cifrar todos los datos
set -x ALLOW_DEFAULT_SECRET 1
python scripts/recrypt_all_data.py
```

El script te pedirá confirmación. Escribe `SI` para continuar.

### Paso 4: Reiniciar y Verificar

```fish
# Reinicia la app
python run.py
```

Ahora deberías ver:
- ✅ Saldos de tarjetas correctos
- ✅ Balances de cuentas visibles
- ✅ **Balance general en el dashboard correcto**
- ✅ Patrimonio neto (Net Worth) actualizado
- ✅ Resumen de deudas con datos reales
- ✅ Montos de transacciones
- ✅ Porcentaje de utilización de tarjetas

## 🔍 Verificación

Para confirmar que todo está bien:

```fish
# Ejecutar diagnóstico de nuevo
set -x ALLOW_DEFAULT_SECRET 1
python scripts/diagnose_encryption.py
```

Deberías ver:
```
✓ APP_MASTER_KEY está configurada
✓ Todas las tarjetas están OK
✓ Todas las cuentas están OK
```

## 📚 Documentación Completa

Para más detalles, consulta: `docs/ENCRYPTION_SETUP.md`

## ⚠️ Notas Importantes

1. **No pierdas la clave:** Sin `APP_MASTER_KEY`, no podrás desencriptar los datos
2. **No la subas a git:** Asegúrate de que `.env` está en `.gitignore`
3. **Usa claves diferentes:** `APP_MASTER_KEY` ≠ `SECRET_KEY`
4. **Producción:** Usa secretos de Kubernetes/Docker/Cloud en lugar de variables de entorno simples

## 🆘 Si Algo Sale Mal

```fish
# Restaurar backup
cp instance/finanzas.db.backup instance/finanzas.db

# Volver a intentar con el diagnóstico
set -x ALLOW_DEFAULT_SECRET 1
python scripts/diagnose_encryption.py
```

## 📞 Necesitas Ayuda?

1. Ejecuta el diagnóstico y comparte el output
2. Verifica que `APP_MASTER_KEY` esté realmente configurada: `echo $APP_MASTER_KEY`
3. Revisa los logs de la aplicación para errores específicos
