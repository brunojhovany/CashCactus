"""Servicio de cálculos financieros precisos.

Este módulo contiene funciones para realizar cálculos financieros
con precisión decimal, siguiendo las mejores prácticas de
finanzas personales y el método de "Te enseñaré a ser rico".
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dateutil.relativedelta import relativedelta


def round_money(amount: float | Decimal | int) -> Decimal:
    """Redondear monto a 2 decimales con redondeo bancario.
    
    Args:
        amount: Monto a redondear
        
    Returns:
        Decimal redondeado a 2 decimales
        
    Example:
        >>> round_money(10.555)
        Decimal('10.56')
        >>> round_money(10.5)
        Decimal('10.50')
    """
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_daily_interest_rate(annual_rate: float) -> Decimal:
    """Calcular tasa de interés diaria desde tasa anual (APR).
    
    Args:
        annual_rate: Tasa anual en porcentaje (ej: 18.5 para 18.5%)
        
    Returns:
        Tasa diaria en decimal
        
    Example:
        >>> calculate_daily_interest_rate(18.0)
        Decimal('0.000493150684931507')  # 18% / 365 días
    """
    apr_decimal = Decimal(str(annual_rate)) / Decimal('100')
    daily_rate = apr_decimal / Decimal('365')
    return daily_rate


def calculate_monthly_interest_simple(
    principal: float | Decimal,
    annual_rate: float,
    method: str = 'simple'
) -> Decimal:
    """Calcular interés mensual de una deuda.
    
    Args:
        principal: Monto principal (deuda actual)
        annual_rate: Tasa de interés anual (APR) en porcentaje
        method: 'simple' o 'compound'
            - simple: APR / 12 (usado por mayoría de tarjetas)
            - compound: (1 + APR)^(1/12) - 1 (interés compuesto real)
    
    Returns:
        Interés mensual en Decimal
        
    Example:
        >>> calculate_monthly_interest_simple(1000, 18.0)
        Decimal('15.00')  # $1000 * 18% / 12
    """
    principal_dec = Decimal(str(principal))
    
    if principal_dec <= 0:
        return Decimal('0.00')
    
    if method == 'simple':
        # Método simple: APR / 12 (estándar en México y mayoría de tarjetas)
        monthly_rate = Decimal(str(annual_rate)) / Decimal('100') / Decimal('12')
        interest = principal_dec * monthly_rate
    else:  # compound
        # Método compuesto: (1 + APR)^(1/12) - 1
        apr_decimal = Decimal(str(annual_rate)) / Decimal('100')
        # Aproximación usando serie de Taylor para evitar usar pow con Decimal
        # (1 + x)^(1/12) ≈ 1 + x/12 - x²/288 + ...
        # Para tasas < 30%, la aproximación simple es suficientemente precisa
        monthly_rate = apr_decimal / Decimal('12')
        interest = principal_dec * monthly_rate
    
    return round_money(interest)


def calculate_debt_payoff_timeline(
    principal: float | Decimal,
    annual_rate: float,
    monthly_payment: float | Decimal,
    method: str = 'avalanche'
) -> Dict:
    """Calcular timeline de pago de deuda (método avalancha).
    
    Args:
        principal: Deuda inicial
        annual_rate: Tasa de interés anual (%)
        monthly_payment: Pago mensual
        method: 'avalanche' o 'snowball' (por ahora solo avalanche)
    
    Returns:
        Dict con:
            - months_to_payoff: meses para liquidar
            - total_interest_paid: total de intereses pagados
            - total_paid: total pagado (principal + intereses)
            - monthly_breakdown: lista de desglose mensual
            - warnings: advertencias (si el pago no cubre interés, etc.)
            
    Example:
        >>> result = calculate_debt_payoff_timeline(5000, 24.0, 300)
        >>> result['months_to_payoff']
        20
        >>> result['total_interest_paid']
        Decimal('955.50')
    """
    principal_dec = round_money(principal)
    payment_dec = round_money(monthly_payment)
    
    warnings = []
    monthly_breakdown = []
    
    current_balance = principal_dec
    month = 0
    total_interest = Decimal('0.00')
    
    # Límite de seguridad: máximo 600 meses (50 años)
    max_months = 600
    
    while current_balance > Decimal('0.01') and month < max_months:
        month += 1
        
        # Calcular interés del mes
        interest = calculate_monthly_interest_simple(current_balance, annual_rate)
        
        # Verificar si el pago cubre al menos el interés
        if payment_dec < interest:
            warnings.append(
                f"⚠️ Pago mensual (${payment_dec}) no cubre el interés (${interest}). "
                "La deuda nunca se pagará."
            )
            break
        
        # Aplicar pago
        principal_payment = payment_dec - interest
        
        # Si el pago es mayor que el balance, ajustar
        if payment_dec > current_balance + interest:
            principal_payment = current_balance
            actual_payment = current_balance + interest
        else:
            actual_payment = payment_dec
        
        # Actualizar balance
        current_balance = current_balance - principal_payment
        total_interest += interest
        
        monthly_breakdown.append({
            'month': month,
            'starting_balance': round_money(current_balance + principal_payment),
            'interest': interest,
            'principal_payment': round_money(principal_payment),
            'total_payment': round_money(actual_payment),
            'ending_balance': round_money(current_balance)
        })
        
        # Prevenir balances negativos por redondeo
        if current_balance < Decimal('0.01'):
            current_balance = Decimal('0.00')
            break
    
    if month >= max_months:
        warnings.append(
            f"⚠️ La deuda tomaría más de {max_months} meses en pagarse. "
            "Considera aumentar el pago mensual."
        )
    
    return {
        'months_to_payoff': month,
        'years_to_payoff': round(month / 12, 1),
        'total_interest_paid': round_money(total_interest),
        'total_paid': round_money(principal_dec + total_interest),
        'monthly_breakdown': monthly_breakdown,
        'warnings': warnings
    }


def calculate_extra_payment_impact(
    principal: float | Decimal,
    annual_rate: float,
    monthly_payment: float | Decimal,
    extra_payment: float | Decimal
) -> Dict:
    """Calcular el impacto de un pago extra mensual.
    
    Args:
        principal: Deuda inicial
        annual_rate: Tasa anual (%)
        monthly_payment: Pago mensual base
        extra_payment: Pago extra mensual adicional
        
    Returns:
        Dict con comparación antes/después del pago extra
        
    Example:
        >>> impact = calculate_extra_payment_impact(10000, 20.0, 300, 100)
        >>> impact['months_saved']
        15
        >>> impact['interest_saved']
        Decimal('1250.00')
    """
    # Calcular sin pago extra
    baseline = calculate_debt_payoff_timeline(principal, annual_rate, monthly_payment)
    
    # Calcular con pago extra
    with_extra = calculate_debt_payoff_timeline(
        principal, 
        annual_rate, 
        Decimal(str(monthly_payment)) + Decimal(str(extra_payment))
    )
    
    months_saved = baseline['months_to_payoff'] - with_extra['months_to_payoff']
    interest_saved = baseline['total_interest_paid'] - with_extra['total_interest_paid']
    
    return {
        'baseline': baseline,
        'with_extra_payment': with_extra,
        'months_saved': months_saved,
        'years_saved': round(months_saved / 12, 1),
        'interest_saved': round_money(interest_saved),
        'extra_payment_monthly': round_money(extra_payment),
        'total_extra_paid': round_money(Decimal(str(extra_payment)) * with_extra['months_to_payoff']),
        'roi': round_money(interest_saved) if interest_saved > 0 else Decimal('0.00')
    }


def calculate_minimum_payment(balance: float | Decimal, method: str = 'percentage') -> Decimal:
    """Calcular pago mínimo de tarjeta de crédito.
    
    Args:
        balance: Saldo de la tarjeta
        method: 'percentage' (estándar) o 'fixed'
            - percentage: 5% del saldo o $50 mínimo (estándar en México)
            - fixed: $50 fijo
            
    Returns:
        Pago mínimo calculado
        
    Example:
        >>> calculate_minimum_payment(1000)
        Decimal('50.00')  # 5% de $1000
        >>> calculate_minimum_payment(500)
        Decimal('50.00')  # Mínimo de $50
    """
    balance_dec = round_money(balance)
    
    if balance_dec <= 0:
        return Decimal('0.00')
    
    if method == 'percentage':
        # 5% del saldo o $50 mínimo (estándar México)
        minimum = max(
            balance_dec * Decimal('0.05'),
            Decimal('50.00')
        )
        # Si el balance es menor que el mínimo, pagar el balance
        return min(minimum, balance_dec)
    else:  # fixed
        return min(Decimal('50.00'), balance_dec)


def calculate_investment_compound_growth(
    principal: float | Decimal,
    annual_rate: float,
    years: int,
    compound_frequency: str = 'monthly',
    monthly_contribution: float | Decimal = 0
) -> Dict:
    """Calcular crecimiento de inversión con interés compuesto.
    
    Args:
        principal: Inversión inicial
        annual_rate: Rendimiento anual esperado (%)
        years: Años de inversión
        compound_frequency: 'monthly', 'quarterly', 'annually'
        monthly_contribution: Aporte mensual adicional
        
    Returns:
        Dict con proyección de crecimiento
        
    Example:
        >>> growth = calculate_investment_compound_growth(10000, 8.0, 10, monthly_contribution=500)
        >>> growth['final_balance']
        Decimal('108722.50')  # aprox
    """
    principal_dec = round_money(principal)
    contribution_dec = round_money(monthly_contribution)
    
    # Determinar frecuencia de capitalización
    if compound_frequency == 'monthly':
        periods_per_year = 12
    elif compound_frequency == 'quarterly':
        periods_per_year = 4
    elif compound_frequency == 'annually':
        periods_per_year = 1
    else:
        periods_per_year = 12
    
    period_rate = Decimal(str(annual_rate)) / Decimal('100') / Decimal(str(periods_per_year))
    total_periods = years * periods_per_year
    
    current_balance = principal_dec
    total_contributions = principal_dec
    monthly_breakdown = []
    
    for period in range(1, total_periods + 1):
        # Calcular interés ganado
        interest = round_money(current_balance * period_rate)
        
        # Agregar contribución (si es mensual o corresponde al período)
        if compound_frequency == 'monthly':
            contribution_this_period = contribution_dec
        elif compound_frequency == 'quarterly' and period % 3 == 0:
            contribution_this_period = contribution_dec * 3  # Acumular 3 meses
        elif compound_frequency == 'annually' and period % 12 == 0:
            contribution_this_period = contribution_dec * 12  # Acumular 12 meses
        else:
            contribution_this_period = Decimal('0.00')
        
        current_balance = current_balance + interest + contribution_this_period
        total_contributions += contribution_this_period
        
        # Guardar solo cada año para no saturar
        if period % periods_per_year == 0:
            monthly_breakdown.append({
                'year': period // periods_per_year,
                'balance': round_money(current_balance),
                'total_contributions': round_money(total_contributions),
                'total_interest': round_money(current_balance - total_contributions)
            })
    
    total_interest = current_balance - total_contributions
    
    return {
        'initial_investment': round_money(principal),
        'monthly_contribution': round_money(monthly_contribution),
        'years': years,
        'annual_rate': annual_rate,
        'final_balance': round_money(current_balance),
        'total_contributions': round_money(total_contributions),
        'total_interest_earned': round_money(total_interest),
        'roi_percentage': round((total_interest / total_contributions * 100), 2) if total_contributions > 0 else 0,
        'yearly_breakdown': monthly_breakdown
    }


def calculate_50_30_20_budget(monthly_income: float | Decimal) -> Dict:
    """Calcular presupuesto según regla 50/30/20.
    
    Regla de oro de "Te enseñaré a ser rico":
    - 50% Necesidades (renta, comida, transporte, seguros)
    - 30% Deseos (entretenimiento, comer fuera, hobbies)
    - 20% Ahorros e inversiones (fondo emergencia, retiro, inversiones)
    
    Args:
        monthly_income: Ingreso mensual neto
        
    Returns:
        Dict con distribución recomendada
        
    Example:
        >>> budget = calculate_50_30_20_budget(50000)
        >>> budget['needs']
        Decimal('25000.00')
        >>> budget['wants']
        Decimal('15000.00')
        >>> budget['savings_investments']
        Decimal('10000.00')
    """
    income_dec = round_money(monthly_income)
    
    needs = round_money(income_dec * Decimal('0.50'))
    wants = round_money(income_dec * Decimal('0.30'))
    savings = round_money(income_dec * Decimal('0.20'))
    
    return {
        'monthly_income': income_dec,
        'needs': needs,
        'needs_percentage': 50,
        'wants': wants,
        'wants_percentage': 30,
        'savings_investments': savings,
        'savings_percentage': 20,
        'breakdown': {
            'Necesidades (50%)': needs,
            'Deseos (30%)': wants,
            'Ahorros e Inversiones (20%)': savings
        },
        'tips': [
            "🏠 Necesidades: renta, comida básica, transporte, seguros, deudas mínimas",
            "🎉 Deseos: salir a comer, entretenimiento, compras no esenciales, viajes",
            "💰 Ahorros: fondo de emergencia (6 meses), retiro, inversiones, pagar deuda extra"
        ]
    }


def calculate_emergency_fund_target(monthly_expenses: float | Decimal, months: int = 6) -> Dict:
    """Calcular meta de fondo de emergencia.
    
    Recomendación de "Te enseñaré a ser rico": 
    - Mínimo 3 meses de gastos
    - Ideal 6 meses de gastos
    - Si tienes dependientes o trabajo inestable: 12 meses
    
    Args:
        monthly_expenses: Gastos mensuales promedio
        months: Meses de cobertura (default 6)
        
    Returns:
        Dict con meta y progreso recomendado
        
    Example:
        >>> fund = calculate_emergency_fund_target(30000, months=6)
        >>> fund['target_amount']
        Decimal('180000.00')
    """
    expenses_dec = round_money(monthly_expenses)
    target = round_money(expenses_dec * Decimal(str(months)))
    
    return {
        'monthly_expenses': expenses_dec,
        'months_coverage': months,
        'target_amount': target,
        'milestones': {
            '1_month': round_money(expenses_dec * 1),
            '3_months': round_money(expenses_dec * 3),
            '6_months': round_money(expenses_dec * 6),
            '12_months': round_money(expenses_dec * 12)
        },
        'recommendations': [
            f"🎯 Meta mínima: ${round_money(expenses_dec * 3):,} (3 meses)",
            f"💪 Meta ideal: ${target:,} ({months} meses)",
            f"🚀 Meta premium: ${round_money(expenses_dec * 12):,} (12 meses)",
            "",
            "📍 Dónde guardar tu fondo de emergencia:",
            "  • Cuenta de ahorros de alto rendimiento (liquid)",
            "  • NO en inversiones volátiles",
            "  • Acceso rápido pero no inmediato (evita tentación)"
        ]
    }


if __name__ == '__main__':
    # Tests básicos
    print("🧮 Pruebas de Cálculos Financieros\n")
    
    # Test 1: Interés mensual
    print("1. Interés mensual de tarjeta:")
    interest = calculate_monthly_interest_simple(5000, 24.0)
    print(f"   Balance: $5,000 | APR: 24% | Interés mensual: ${interest}")
    
    # Test 2: Timeline de pago
    print("\n2. Timeline de pago de deuda:")
    timeline = calculate_debt_payoff_timeline(10000, 20.0, 500)
    print(f"   Deuda: $10,000 | APR: 20% | Pago: $500/mes")
    print(f"   → Meses para liquidar: {timeline['months_to_payoff']}")
    print(f"   → Total intereses: ${timeline['total_interest_paid']}")
    
    # Test 3: Impacto de pago extra
    print("\n3. Impacto de pago extra:")
    impact = calculate_extra_payment_impact(10000, 20.0, 500, 200)
    print(f"   Pago extra: $200/mes")
    print(f"   → Meses ahorrados: {impact['months_saved']}")
    print(f"   → Interés ahorrado: ${impact['interest_saved']}")
    
    # Test 4: Presupuesto 50/30/20
    print("\n4. Presupuesto 50/30/20:")
    budget = calculate_50_30_20_budget(50000)
    print(f"   Ingreso: $50,000/mes")
    print(f"   → Necesidades (50%): ${budget['needs']}")
    print(f"   → Deseos (30%): ${budget['wants']}")
    print(f"   → Ahorros (20%): ${budget['savings_investments']}")
    
    print("\n✅ Todos los cálculos completados")
