# Configuración de Cifrado - Guía de Solución

## Problema: Datos aparecen como ceros

Si ves que los saldos de tarjetas, cuentas o transacciones aparecen como ceros, es muy probable que el problema sea con la **clave maestra de cifrado** (`APP_MASTER_KEY`).

### ¿Por qué sucede esto?

La aplicación usa cifrado AES-256-GCM para proteger datos sensibles (saldos, descripciones, etc.). Cuando la aplicación se inicia sin una `APP_MASTER_KEY` configurada:

1. Se genera una clave **efímera** (temporal) automáticamente
2. Los datos nuevos se cifran con esta clave efímera
3. **Al reiniciar la app**, se genera una clave efímera DIFERENTE
4. Los datos cifrados con la clave anterior **no se pueden desencriptar**
5. Resultado: los campos cifrados devuelven `None` → se muestran como `0`

## Solución Paso a Paso

### 1. Generar una Clave Maestra Permanente

Ejecuta este comando para generar una clave segura:

```bash
python3 -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'
```

Ejemplo de salida:
```
dGhpc2lzYW5leGFtcGxla2V5Zm9yZGVtb3B1cnBvc2VzMTIz
```

**IMPORTANTE:** Guarda esta clave en un lugar seguro. Si la pierdes, no podrás recuperar los datos cifrados.

### 2. Configurar la Clave Según tu Entorno

#### Opción A: Desarrollo Local (Fish Shell)

```fish
# Configurar para la sesión actual
set -x APP_MASTER_KEY "tu-clave-generada-aqui"

# O guardar permanentemente en config.fish
echo 'set -x APP_MASTER_KEY "tu-clave-generada-aqui"' >> ~/.config/fish/config.fish
```

#### Opción B: Desarrollo Local (Bash/Zsh)

```bash
# Configurar para la sesión actual
export APP_MASTER_KEY="tu-clave-generada-aqui"

# O guardar permanentemente
echo 'export APP_MASTER_KEY="tu-clave-generada-aqui"' >> ~/.bashrc
# O para Zsh:
echo 'export APP_MASTER_KEY="tu-clave-generada-aqui"' >> ~/.zshrc
```

#### Opción C: Archivo .env

Crea o edita el archivo `.env` en la raíz del proyecto:

```bash
APP_MASTER_KEY=tu-clave-generada-aqui
APP_ENC_ACTIVE_VERSION=1
SECRET_KEY=otra-clave-secreta-diferente
```

Luego carga las variables antes de iniciar la app:

```bash
# Si usas python-dotenv (ya incluido en requirements.txt)
# La app automáticamente carga .env

# O manualmente:
export $(cat .env | xargs)
```

#### Opción D: Docker/Kubernetes

**Docker Compose:**
```yaml
services:
  app:
    environment:
      - APP_MASTER_KEY=tu-clave-generada-aqui
      - APP_ENC_ACTIVE_VERSION=1
```

**Kubernetes Secret:**
```bash
kubectl create secret generic app-secrets \
  --from-literal=APP_MASTER_KEY=tu-clave-generada-aqui
```

**Deployment:**
```yaml
env:
  - name: APP_MASTER_KEY
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: APP_MASTER_KEY
```

#### Opción E: Servicios en la Nube

**Heroku:**
```bash
heroku config:set APP_MASTER_KEY=tu-clave-generada-aqui
```

**AWS Elastic Beanstalk:**
```bash
aws elasticbeanstalk update-environment \
  --environment-name tu-env \
  --option-settings Namespace=aws:elasticbeanstalk:application:environment,OptionName=APP_MASTER_KEY,Value=tu-clave-generada-aqui
```

**Google Cloud Run:**
```bash
gcloud run services update tu-servicio \
  --update-env-vars APP_MASTER_KEY=tu-clave-generada-aqui
```

### 3. Ejecutar Diagnóstico

Antes de re-cifrar, ejecuta el script de diagnóstico para ver el estado actual:

```bash
python scripts/diagnose_encryption.py
```

Este script te mostrará:
- Si `APP_MASTER_KEY` está configurada
- Qué tarjetas/cuentas tienen problemas de cifrado
- Discrepancias entre saldos cifrados y calculados
- Recomendaciones específicas

### 4. Re-cifrar los Datos Existentes

**⚠️ IMPORTANTE: Haz un backup de tu base de datos primero**

```bash
# Backup de SQLite
cp instance/finanzas.db instance/finanzas.db.backup

# Backup de PostgreSQL
pg_dump tu_base_de_datos > backup.sql
```

Luego ejecuta el script de re-cifrado:

```bash
python scripts/recrypt_all_data.py
```

Este script:
1. Verifica que `APP_MASTER_KEY` esté configurada
2. Recalcula todos los saldos desde las transacciones
3. Re-cifra todos los datos con la clave maestra actual
4. Actualiza la versión de cifrado

### 5. Reiniciar y Verificar

```bash
# Reinicia la aplicación
python run.py

# O si usas gunicorn:
gunicorn -c gunicorn_config.py run:app
```

Verifica que:
- Los saldos de tarjetas se muestran correctamente
- Las cuentas muestran el balance correcto
- Las transacciones tienen sus montos visibles
- El porcentaje de utilización de tarjetas no es 0%

## Prevención Futura

### Checklist de Configuración Correcta

- [ ] `APP_MASTER_KEY` está configurada y es persistente
- [ ] La clave tiene al menos 32 bytes (44+ caracteres en base64)
- [ ] `APP_ENC_ACTIVE_VERSION=1` está configurada
- [ ] Las variables se cargan **antes** de iniciar la app
- [ ] Tienes backup de la clave en un lugar seguro
- [ ] La clave **NO** está en el repositorio git (usa `.env` y `.gitignore`)

### Verificación Rápida

```bash
# Verificar que la clave está cargada
echo $APP_MASTER_KEY

# Debe mostrar tu clave, no estar vacío
```

### Si Usas Múltiples Entornos

Mantén claves diferentes para cada entorno:

```bash
# Desarrollo
APP_MASTER_KEY_DEV=clave-para-desarrollo

# Staging
APP_MASTER_KEY_STAGING=clave-para-staging

# Producción
APP_MASTER_KEY_PROD=clave-para-produccion
```

## Troubleshooting

### "Los datos aún aparecen como ceros"

1. Verifica que `APP_MASTER_KEY` esté exportada:
   ```bash
   echo $APP_MASTER_KEY
   ```

2. Reinicia completamente la aplicación (no solo reload)

3. Ejecuta el diagnóstico de nuevo:
   ```bash
   python scripts/diagnose_encryption.py
   ```

4. Si persiste, ejecuta el re-cifrado de nuevo

### "Error: No se encontró llave maestra"

Significa que `APP_MASTER_KEY` no está en las variables de entorno cuando la app inicia.

Solución:
```bash
export APP_MASTER_KEY="tu-clave"
python run.py
```

### "Los datos antiguos no se pueden recuperar"

Si cambiaste la clave y no tienes la anterior, los datos cifrados con la clave vieja están perdidos.

Opciones:
1. Restaurar desde backup
2. Re-crear los datos manualmente
3. Usar el script de re-cifrado para recalcular saldos desde transacciones

## Rotación de Claves (Avanzado)

Para rotar claves sin perder datos:

1. Configura una nueva versión:
   ```bash
   export APP_MASTER_KEY_2="nueva-clave-aqui"
   export APP_ENC_ACTIVE_VERSION=2
   ```

2. La app seguirá desencriptando datos v1 con la clave v1
3. Los datos nuevos se cifrarán con v2
4. Ejecuta migración gradual cuando estés listo

## Soporte

Si necesitas ayuda:
1. Ejecuta `python scripts/diagnose_encryption.py` y comparte el output
2. Verifica los logs de la aplicación
3. Revisa que las variables de entorno estén correctamente configuradas
