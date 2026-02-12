# Función: Eliminar Todos los Datos del Usuario

## 📋 Descripción

Permite a los usuarios eliminar todos sus registros financieros de la aplicación de forma permanente, manteniendo su cuenta activa pero sin datos.

## ✨ Funcionalidades

### Qué se Elimina

✅ **Todas las transacciones** del usuario
✅ **Todas las cuentas bancarias** (ahorro, corriente, inversiones)
✅ **Todas las tarjetas de crédito**
✅ **Todas las cuentas de deuda**
✅ **Todos los recordatorios**
✅ **Ingreso mensual** (se resetea a 0)

### Qué se Mantiene

✅ **Cuenta de usuario** (username, email, contraseña)
✅ **Nombre y apellido**
✅ **Fecha de registro**
✅ **Configuraciones OAuth** (si aplica)

## 🔐 Seguridad

### Medidas de Protección

1. **Autenticación requerida**: Usuario debe estar logueado
2. **Confirmación de contraseña**: Requiere contraseña actual para proceder
3. **Doble confirmación**: 
   - Página de advertencia con descripción detallada
   - Confirmación JavaScript antes de enviar
4. **Transacción atómica**: Todo se elimina en una transacción o nada

### Flujo de Confirmación

```
Perfil → Zona de Peligro → Página de Advertencia → 
Ingresar Contraseña → Confirmación JS → Eliminación
```

## 🗂️ Archivos Creados/Modificados

### Nuevos Archivos

- **`app/views/templates/auth/profile.html`**
  - Página de perfil del usuario
  - Sección "Zona de Peligro" con acceso a eliminación

- **`app/views/templates/auth/delete_data.html`**
  - Página de confirmación de eliminación
  - Advertencias claras sobre consecuencias
  - Formulario de confirmación con contraseña

### Archivos Modificados

- **`app/controllers/auth_controller.py`**
  - Agregado método `delete_all_data()`
  - Validación de contraseña
  - Eliminación en cascada de todos los registros

- **`app/routes.py`**
  - Nueva ruta: `/delete-all-data` (GET, POST)
  - Protegida con `@login_required`

### Archivos Base (No Modificados)

- **`app/views/templates/base.html`**
  - Ya tenía enlace a perfil en dropdown de usuario
  - No requirió modificaciones

## 🎯 Uso

### Para el Usuario

1. Ir a **Perfil** (icono de usuario en header)
2. Buscar sección **"Zona de Peligro"**
3. Hacer clic en **"Eliminar Todos Mis Datos"**
4. Leer advertencias cuidadosamente
5. Ingresar contraseña actual
6. Confirmar en popup JavaScript
7. Los datos se eliminan permanentemente

### Código de Ejemplo

```python
# En auth_controller.py
@staticmethod
@login_required
def delete_all_data():
    """Eliminar todos los datos del usuario"""
    if request.method == 'POST':
        # Verificar contraseña
        password = request.form.get('confirm_password')
        if not current_user.check_password(password):
            flash('Contraseña incorrecta.', 'error')
            return redirect(url_for('auth.profile'))
        
        # Eliminar todos los registros
        Transaction.query.filter_by(user_id=user_id).delete()
        Reminder.query.filter_by(user_id=user_id).delete()
        CreditCard.query.filter_by(user_id=user_id).delete()
        Account.query.filter_by(user_id=user_id).delete()
        
        # Resetear campos
        current_user.monthly_income = 0.0
        
        db.session.commit()
        return redirect(url_for('main.dashboard'))
```

## ⚠️ Advertencias

### Para Desarrolladores

- **No hay backup automático**: Considerar agregar función de exportación antes de eliminar
- **Irreversible**: No hay manera de recuperar datos eliminados
- **Cascada en DB**: Asegurarse que las relaciones tengan `cascade='all, delete-orphan'`

### Para Usuarios

- ⚠️ **PERMANENTE**: Los datos no pueden recuperarse
- 📊 **Exporta primero**: Si necesitas tus datos, expórtalos antes
- 🔄 **Cuenta activa**: Tu cuenta permanece, solo se eliminan registros
- 💳 **Todo se borra**: Transacciones, cuentas, tarjetas, TODO

## 🔄 Mejoras Futuras

### Sugerencias de Implementación

1. **Exportación previa**
   - Botón "Exportar mis datos antes de eliminar"
   - Generar CSV/Excel con todos los registros
   - Enviar por email

2. **Soft Delete**
   - Marcar registros como "deleted" en lugar de eliminar
   - Permitir recuperación dentro de 30 días
   - Limpieza automática después de período de gracia

3. **Eliminación programada**
   - "Eliminar en 7 días"
   - Enviar emails de confirmación
   - Permitir cancelación

4. **Logs de auditoría**
   - Registrar qué usuario eliminó datos
   - Timestamp de eliminación
   - IP y user agent

5. **Estadísticas previas**
   - Mostrar resumen de datos a eliminar
   - "Eliminarás X transacciones, Y cuentas..."

## 🧪 Testing

### Casos a Probar

```bash
# 1. Acceso no autorizado
curl -X GET http://localhost:5000/delete-all-data
# Debe redirigir a login

# 2. Contraseña incorrecta
# Ingresar contraseña errónea → debe rechazar

# 3. Eliminación exitosa
# Verificar que todos los registros se eliminen
# Verificar que usuario siga existiendo

# 4. Rollback en error
# Simular error durante eliminación
# Verificar que NO se elimine nada
```

## 📝 Checklist de Implementación

- [x] ✅ Método `delete_all_data()` en AuthController
- [x] ✅ Ruta `/delete-all-data` en routes.py
- [x] ✅ Template de confirmación `delete_data.html`
- [x] ✅ Template de perfil `profile.html`
- [x] ✅ Validación de contraseña
- [x] ✅ Confirmación JavaScript
- [x] ✅ Transacción atómica (commit/rollback)
- [x] ✅ Mensajes flash informativos
- [x] ✅ Enlace en menú de usuario
- [x] ✅ Diseño responsive
- [ ] ⏳ Función de exportación previa (futuro)
- [ ] ⏳ Tests unitarios (futuro)
- [ ] ⏳ Logs de auditoría (futuro)

## 🎨 UI/UX

### Diseño

- **Colores**: Rojo para zona de peligro (Bootstrap danger)
- **Iconos**: Font Awesome exclamation-triangle, trash-alt
- **Confirmaciones**: Múltiples niveles de advertencia
- **Responsive**: Funciona en móvil y escritorio

### Mensajes

- **Éxito**: "Todos tus datos han sido eliminados exitosamente"
- **Error contraseña**: "Contraseña incorrecta. No se eliminaron los datos"
- **Error general**: "Error al eliminar los datos. Por favor intenta nuevamente"

---

**Fecha de Implementación**: 5 de Febrero, 2026
**Prioridad**: Cumplimiento GDPR / Privacidad del Usuario
**Estado**: ✅ Completado y Listo para Uso
