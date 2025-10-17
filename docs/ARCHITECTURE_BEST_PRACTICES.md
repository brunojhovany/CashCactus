# 🏗️ Arquitectura y Mejores Prácticas

## Refactorización: De Rutas a Servicios

### ❌ Antes (Mala Práctica)

```python
# app/routes.py
from app import db
from app.models.account import Account
from app.models.credit_card import CreditCard

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # ❌ Lógica de negocio en las rutas
    # ❌ Acceso directo a DB desde rutas
    # ❌ Manejo de errores repetido
    # ❌ Código duplicado
    
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    for account in accounts:
        try:
            account.update_balance()
        except Exception:
            pass
    
    cards = CreditCard.query.filter_by(user_id=current_user.id).all()
    for card in cards:
        try:
            card.update_balance()
        except Exception:
            pass
    
    db.session.commit()
    
    # ... renderizar template
```

**Problemas:**
- 🔴 Las rutas tienen lógica de negocio
- 🔴 Acceso directo a DB desde controladores
- 🔴 Difícil de testear
- 🔴 Código duplicado en múltiples lugares
- 🔴 Violación de Single Responsibility Principle
- 🔴 Acoplamiento alto

### ✅ Después (Buena Práctica)

```python
# app/routes.py
from app.services.balance_maintenance_service import BalanceMaintenanceService

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # ✅ Delega lógica de negocio a servicio
    # ✅ No toca DB directamente
    # ✅ Código limpio y mantenible
    
    BalanceMaintenanceService.recalculate_user_balances(current_user.id)
    
    # ... renderizar template
```

```python
# app/services/balance_maintenance_service.py
class BalanceMaintenanceService:
    """Servicio centralizado para mantenimiento de saldos."""
    
    @staticmethod
    def recalculate_user_balances(user_id: int) -> dict:
        """
        Recalcula todos los saldos de un usuario.
        
        Returns:
            dict con estadísticas: accounts_updated, cards_updated, errors
        """
        stats = {'accounts_updated': 0, 'cards_updated': 0, 'errors': []}
        
        try:
            accounts = Account.query.filter_by(user_id=user_id).all()
            for account in accounts:
                try:
                    account.update_balance()
                    stats['accounts_updated'] += 1
                except Exception as e:
                    stats['errors'].append(f"Account {account.id}: {str(e)}")
            
            cards = CreditCard.query.filter_by(user_id=user_id).all()
            for card in cards:
                try:
                    card.update_balance()
                    stats['cards_updated'] += 1
                except Exception as e:
                    stats['errors'].append(f"Card {card.id}: {str(e)}")
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            stats['errors'].append(str(e))
        
        return stats
```

**Ventajas:**
- ✅ Separación de concerns
- ✅ Código reutilizable
- ✅ Fácil de testear
- ✅ Mejor manejo de errores
- ✅ Estadísticas de operación
- ✅ Documentación clara

## Arquitectura por Capas

```
┌─────────────────────────────────────┐
│         CAPA DE PRESENTACIÓN        │
│   (Routes, Templates, Controllers)  │
│                                     │
│  - Recibe requests HTTP             │
│  - Delega a servicios               │
│  - Renderiza respuestas             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      CAPA DE LÓGICA DE NEGOCIO      │
│           (Services)                │
│                                     │
│  - ReportService                    │
│  - BalanceMaintenanceService        │
│  - PaymentReminderService           │
│  - DailyMaintenanceService          │
│                                     │
│  Responsable de:                    │
│  - Validaciones de negocio          │
│  - Cálculos complejos               │
│  - Orquestación de operaciones      │
│  - Manejo de errores                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      CAPA DE ACCESO A DATOS         │
│           (Models)                  │
│                                     │
│  - Account                          │
│  - CreditCard                       │
│  - Transaction                      │
│  - User                             │
│                                     │
│  Responsable de:                    │
│  - Definición de esquema            │
│  - Operaciones CRUD básicas         │
│  - Validaciones de integridad       │
│  - Cifrado/descifrado               │
└─────────────────────────────────────┘
```

## Principios SOLID Aplicados

### 1. Single Responsibility Principle (SRP)

**Antes:**
```python
# routes.py hacía demasiado:
# - Routing
# - Lógica de negocio
# - Acceso a DB
# - Manejo de errores
```

**Ahora:**
```python
# routes.py: Solo routing
@main_bp.route('/dashboard')
def dashboard():
    BalanceMaintenanceService.recalculate_user_balances(current_user.id)
    return render_template(...)

# BalanceMaintenanceService: Solo mantenimiento de balances
class BalanceMaintenanceService:
    @staticmethod
    def recalculate_user_balances(user_id: int):
        # Lógica específica de recalculo

# Models: Solo acceso a datos
class CreditCard(db.Model):
    def update_balance(self):
        # Lógica de actualización
```

### 2. Open/Closed Principle (OCP)

El servicio es **abierto para extensión** pero **cerrado para modificación**:

```python
# Podemos agregar nuevos métodos sin modificar los existentes
class BalanceMaintenanceService:
    @staticmethod
    def recalculate_user_balances(user_id: int):
        # Existente
        
    @staticmethod
    def recalculate_all_balances():
        # Nuevo método, no modifica el anterior
        
    @staticmethod
    def fix_card_balance(card_id: int, user_id: int):
        # Nuevo método, no modifica los anteriores
```

### 3. Dependency Inversion Principle (DIP)

```python
# Las rutas NO dependen de implementaciones concretas
# Dependen de abstracciones (interfaces de servicio)

@main_bp.route('/dashboard')
def dashboard():
    # No sabe CÓMO se recalculan los balances
    # Solo sabe QUÉ hacer
    BalanceMaintenanceService.recalculate_user_balances(current_user.id)
```

## Beneficios de Esta Arquitectura

### 1. **Testabilidad**

```python
# Fácil de testear el servicio sin HTTP
def test_recalculate_balances():
    stats = BalanceMaintenanceService.recalculate_user_balances(user_id=1)
    assert stats['accounts_updated'] > 0
    assert len(stats['errors']) == 0
```

### 2. **Reutilización**

```python
# El mismo servicio se usa en múltiples lugares
@main_bp.route('/dashboard')
def dashboard():
    BalanceMaintenanceService.recalculate_user_balances(current_user.id)

@main_bp.route('/accounts')
def accounts():
    BalanceMaintenanceService.recalculate_user_balances(current_user.id)

# Script de mantenimiento
def daily_maintenance():
    BalanceMaintenanceService.recalculate_all_balances()
```

### 3. **Mantenibilidad**

```python
# Si necesitas cambiar la lógica de recalculo:
# - Solo modificas BalanceMaintenanceService
# - Todos los lugares que lo usan se benefician
# - No necesitas buscar y reemplazar en múltiples archivos
```

### 4. **Debugging**

```python
# Los servicios retornan estadísticas
stats = BalanceMaintenanceService.recalculate_user_balances(user_id)

if stats['errors']:
    logger.error(f"Errors during recalculation: {stats['errors']}")
    
logger.info(f"Updated {stats['accounts_updated']} accounts, {stats['cards_updated']} cards")
```

## Comparación Directa

| Aspecto | Antes (Rutas con DB) | Después (Servicios) |
|---------|---------------------|---------------------|
| **Separación de Concerns** | ❌ Mezclado | ✅ Separado |
| **Testabilidad** | ❌ Difícil | ✅ Fácil |
| **Reutilización** | ❌ Código duplicado | ✅ Un solo lugar |
| **Mantenibilidad** | ❌ Cambios en múltiples lugares | ✅ Cambio en un lugar |
| **Estadísticas** | ❌ No disponibles | ✅ Disponibles |
| **Manejo de Errores** | ❌ Básico | ✅ Robusto |
| **Logging** | ❌ Difícil | ✅ Centralizado |
| **Acoplamiento** | ❌ Alto | ✅ Bajo |

## Patrón de Diseño Aplicado

### Service Layer Pattern

```
┌──────────────┐
│   Route      │  ← Solo conoce servicios
└──────┬───────┘
       │ usa
       ▼
┌──────────────┐
│   Service    │  ← Orquesta operaciones de negocio
└──────┬───────┘
       │ usa
       ▼
┌──────────────┐
│   Model      │  ← Solo operaciones CRUD
└──────────────┘
```

**Características:**
- Servicios son **stateless** (sin estado)
- Servicios usan **métodos estáticos** para facilitar uso
- Un servicio puede usar **múltiples modelos**
- Servicios **retornan datos**, no objetos Flask
- Servicios **manejan transacciones** completas

## Mejores Prácticas Adicionales

### 1. Documentación Clara

```python
@staticmethod
def recalculate_user_balances(user_id: int) -> dict:
    """
    Recalcula todos los saldos de cuentas y tarjetas de un usuario.
    
    Útil para:
    - Corregir problemas de cifrado
    - Sincronizar saldos con transacciones
    - Mantenimiento preventivo
    
    Args:
        user_id: ID del usuario
        
    Returns:
        dict con estadísticas de la operación
        
    Raises:
        No lanza excepciones; las captura y las incluye en 'errors'
    """
```

### 2. Type Hints

```python
def recalculate_user_balances(user_id: int) -> dict:
    # Type hints ayudan a IDEs y linters
```

### 3. Retorno Consistente

```python
# Siempre retornar diccionarios con la misma estructura
return {
    'accounts_updated': int,
    'cards_updated': int,
    'errors': list
}
```

### 4. Manejo Graceful de Errores

```python
# No fallar por un error en un elemento
for account in accounts:
    try:
        account.update_balance()
        stats['accounts_updated'] += 1
    except Exception as e:
        stats['errors'].append(f"Account {account.id}: {str(e)}")
        # Continúa con el siguiente
```

## Conclusión

La refactorización de rutas con DB a servicios dedicados:

✅ **Mejora la calidad del código**  
✅ **Facilita el mantenimiento**  
✅ **Hace el código más testeable**  
✅ **Reduce el acoplamiento**  
✅ **Sigue principios SOLID**  
✅ **Aplica patrones de diseño probados**  

Es un ejemplo de **ingeniería de software profesional** que hace el código más robusto, mantenible y escalable.
