from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Para generar gráficos sin GUI
import io
import base64
import numpy as np
from app.models.transaction import Transaction
from app.models.account import Account
from app.models.credit_card import CreditCard

class ReportService:
    """Servicio para generar reportes financieros"""
    
    @staticmethod
    def get_monthly_summary(user_id, year, month):
        """Obtener resumen mensual de finanzas"""
        # Fechas del mes
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Transacciones del mes
        transactions = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.date >= start_date,
            Transaction.date < end_date
        ).all()
        
        # Calcular totales
        # Nota: Los pagos a tarjetas de crédito se registran como 'income' en la entidad
        # Transaction cuando están asociados a una tarjeta (credit_card_id != None),
        # ya que reducen la deuda de la tarjeta. Sin embargo, eso no debe contarse
        # como ingreso real en los reportes (dashboard). Por eso se excluyen.
        total_income = sum(
            t.amount for t in transactions
            if t.transaction_type == 'income' and t.credit_card_id is None
        )
        total_expenses = sum(t.amount for t in transactions if t.transaction_type == 'expense')
        net_income = total_income - total_expenses
        
        # Gastos por categoría
        expenses_by_category = {}
        for transaction in transactions:
            if transaction.transaction_type == 'expense':
                category = transaction.get_category_display()
                expenses_by_category[category] = expenses_by_category.get(category, 0) + transaction.amount
        
        return {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_income': net_income,
            'expenses_by_category': expenses_by_category,
            'transaction_count': len(transactions)
        }
    
    @staticmethod
    def get_quarterly_report(user_id, year, quarter):
        """Obtener reporte trimestral"""
        # Calcular meses del trimestre
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        
        # Obtener datos de cada mes del trimestre
        monthly_data = []
        for month in range(start_month, end_month + 1):
            monthly_summary = ReportService.get_monthly_summary(user_id, year, month)
            monthly_summary['month'] = month
            monthly_summary['month_name'] = datetime(year, month, 1).strftime('%B')
            monthly_data.append(monthly_summary)
        
        # Calcular totales del trimestre
        total_income = sum(data['total_income'] for data in monthly_data)
        total_expenses = sum(data['total_expenses'] for data in monthly_data)
        net_income = total_income - total_expenses
        
        # Promedio mensual
        avg_monthly_income = total_income / 3
        avg_monthly_expenses = total_expenses / 3
        
        # Tendencia (comparar primer mes con último mes)
        if len(monthly_data) >= 2:
            income_trend = monthly_data[-1]['total_income'] - monthly_data[0]['total_income']
            expense_trend = monthly_data[-1]['total_expenses'] - monthly_data[0]['total_expenses']
        else:
            income_trend = 0
            expense_trend = 0
        
        return {
            'quarter': quarter,
            'year': year,
            'monthly_data': monthly_data,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_income': net_income,
            'avg_monthly_income': avg_monthly_income,
            'avg_monthly_expenses': avg_monthly_expenses,
            'income_trend': income_trend,
            'expense_trend': expense_trend
        }
    
    @staticmethod
    def get_debt_summary(user_id):
        """Obtener resumen completo de deudas (tarjetas + cuentas de deuda)"""
        # Tarjetas de crédito
        credit_cards = CreditCard.query.filter_by(user_id=user_id, is_active=True).all()
        
        # Cuentas de deuda
        debt_accounts = Account.query.filter_by(
            user_id=user_id, 
            is_debt_account=True, 
            is_active=True
        ).all()
        
        # Calcular totales de tarjetas de crédito
        credit_card_debt = sum(card.current_balance for card in credit_cards)
        total_credit_limit = sum(card.credit_limit for card in credit_cards)
        total_available_credit = total_credit_limit - credit_card_debt
        
        # Calcular totales de cuentas de deuda (balance positivo = deuda pendiente)
        account_debt = sum(account.balance for account in debt_accounts if account.balance > 0)
        
        # Total general de deudas
        total_debt = credit_card_debt + account_debt
        
        # Utilización promedio de tarjetas
        if total_credit_limit > 0:
            utilization_percentage = (credit_card_debt / total_credit_limit) * 100
        else:
            utilization_percentage = 0
        
        # Pagos mínimos totales
        credit_card_minimum = sum(card.minimum_payment for card in credit_cards)
        debt_account_minimum = sum(account.minimum_payment for account in debt_accounts)
        total_minimum_payment = credit_card_minimum + debt_account_minimum
        
        # Intereses mensuales estimados
        monthly_interest = 0
        for account in debt_accounts:
            monthly_interest += account.calculate_monthly_interest()
        
        # Próximos vencimientos
        upcoming_payments = []
        
        # Vencimientos de tarjetas de crédito
        for card in credit_cards:
            if card.current_balance > 0:
                next_due_datetime = card.get_next_due_date()
                next_due_date = next_due_datetime.date() if next_due_datetime else None
                
                if next_due_date:
                    from datetime import date
                    days_until = (next_due_date - date.today()).days
                else:
                    days_until = 0
                
                upcoming_payments.append({
                    'type': 'credit_card',
                    'name': card.name,
                    'amount': card.minimum_payment,
                    'due_date': next_due_date,
                    'days_until_due': days_until,
                    'is_overdue': days_until < 0
                })
        
        # Vencimientos de cuentas de deuda
        for account in debt_accounts:
            if account.balance > 0:  # Hay deuda pendiente (balance positivo)
                next_due = account.get_next_payment_due_date()
                if next_due:
                    from datetime import date
                    days_until = (next_due - date.today()).days
                    upcoming_payments.append({
                        'type': 'debt_account',
                        'name': account.name,
                        'creditor': account.creditor_name,
                        'amount': account.minimum_payment,
                        'due_date': next_due,
                        'days_until_due': days_until,
                        'is_overdue': account.is_payment_overdue()
                    })
        
        # Ordenar por fecha de vencimiento
        # Convertir todas las fechas a date() para evitar errores de comparación
        def get_sort_key(payment):
            due_date = payment.get('due_date')
            if due_date is None:
                return datetime.max.date()
            elif isinstance(due_date, datetime):
                return due_date.date()
            else:
                return due_date
        
        upcoming_payments.sort(key=get_sort_key)
        
        return {
            'total_debt': total_debt,
            'credit_card_debt': credit_card_debt,
            'account_debt': account_debt,
            'total_credit_limit': total_credit_limit,
            'total_available_credit': total_available_credit,
            'utilization_percentage': utilization_percentage,
            'total_minimum_payment': total_minimum_payment,
            'monthly_interest': monthly_interest,
            'upcoming_payments': upcoming_payments,
            'credit_card_count': len(credit_cards),
            'debt_account_count': len(debt_accounts),
            'total_debt_accounts': len(credit_cards) + len(debt_accounts),
            'overdue_payments': len([p for p in upcoming_payments if p.get('is_overdue', False)])
        }
    
    @staticmethod
    def get_net_worth(user_id):
        """Calcular patrimonio neto incluyendo cuentas de deuda"""
        # Activos (saldos positivos de cuentas normales)
        normal_accounts = Account.query.filter_by(
            user_id=user_id, 
            is_active=True, 
            is_debt_account=False
        ).all()
        total_assets = sum(account.balance for account in normal_accounts)
        
        # Pasivos de tarjetas de crédito
        credit_cards = CreditCard.query.filter_by(user_id=user_id, is_active=True).all()
        credit_card_debt = sum(card.current_balance for card in credit_cards)
        
        # Pasivos de cuentas de deuda (balances positivos = deuda pendiente)
        debt_accounts = Account.query.filter_by(
            user_id=user_id, 
            is_active=True, 
            is_debt_account=True
        ).all()
        account_debt = sum(account.balance for account in debt_accounts if account.balance > 0)
        
        # Total de pasivos
        total_liabilities = credit_card_debt + account_debt
        
        # Patrimonio neto
        net_worth = total_assets - total_liabilities
        
        return {
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'credit_card_debt': credit_card_debt,
            'account_debt': account_debt,
            'net_worth': net_worth,
            'debt_to_asset_ratio': (total_liabilities / total_assets * 100) if total_assets > 0 else 0
        }
    
    @staticmethod
    def generate_expense_chart(user_id, year, month):
        """Generar gráfico de gastos por categoría"""
        monthly_summary = ReportService.get_monthly_summary(user_id, year, month)
        expenses_by_category = monthly_summary['expenses_by_category']
        
        if not expenses_by_category:
            return None
        
        # Crear gráfico de pastel
        plt.figure(figsize=(10, 8))
        categories = list(expenses_by_category.keys())
        amounts = list(expenses_by_category.values())
        
        plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=90)
        plt.title(f'Gastos por Categoría - {datetime(year, month, 1).strftime("%B %Y")}')
        
        # Convertir a base64 para mostrar en HTML
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight')
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data
    
    @staticmethod
    def generate_income_expense_trend(user_id, year):
        """Generar gráfico de tendencia de ingresos y gastos"""
        monthly_data = []
        
        for month in range(1, 13):
            summary = ReportService.get_monthly_summary(user_id, year, month)
            monthly_data.append({
                'month': month,
                'month_name': datetime(year, month, 1).strftime('%b'),
                'income': summary['total_income'],
                'expenses': summary['total_expenses']
            })
        
        # Crear gráfico de líneas con regresión lineal (x numérico y etiquetas de mes)
        plt.figure(figsize=(12, 6))
        month_labels = [data['month_name'] for data in monthly_data]
        x = np.arange(1, 13)
        incomes = np.array([data['income'] for data in monthly_data], dtype=float)
        expenses = np.array([data['expenses'] for data in monthly_data], dtype=float)

        # Series originales
        plt.plot(x, incomes, marker='o', label='Ingresos', linewidth=2)
        plt.plot(x, expenses, marker='s', label='Gastos', linewidth=2)

        # Regresión lineal: y = m*x + b
        try:
            m_inc, b_inc = np.polyfit(x, incomes, 1)
            y_inc_fit = m_inc * x + b_inc
            plt.plot(x, y_inc_fit, linestyle='--', alpha=0.7, label='Regresión ingresos')
        except Exception:
            pass

        try:
            m_exp, b_exp = np.polyfit(x, expenses, 1)
            y_exp_fit = m_exp * x + b_exp
            plt.plot(x, y_exp_fit, linestyle='--', alpha=0.7, label='Regresión gastos')
        except Exception:
            pass

        plt.title(f'Tendencia de Ingresos y Gastos - {year}')
        plt.xlabel('Mes')
        plt.ylabel('Monto ($)')
        plt.grid(True, alpha=0.3)
        plt.xticks(x, month_labels, rotation=45)
        plt.legend()
        
        # Convertir a base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight')
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data

    @staticmethod
    def generate_assets_liabilities_pie(user_id):
        """Generar gráfico de pastel de activos vs pasivos"""
        net_worth_data = ReportService.get_net_worth(user_id)
        
        # Datos para el gráfico
        labels = ['Activos', 'Pasivos']
        sizes = [net_worth_data['total_assets'], net_worth_data['total_liabilities']]
        colors = ['#28a745', '#dc3545']
        explode = (0.05, 0)  # Explotar la primera rebanada
        
        if sum(sizes) == 0:
            return None
        
        plt.figure(figsize=(8, 8))
        plt.pie(sizes, explode=explode, labels=labels, colors=colors,
                autopct='%1.1f%%', shadow=True, startangle=90)
        plt.title('Distribución de Patrimonio\nActivos vs Pasivos', fontsize=14, fontweight='bold')
        
        # Agregar leyenda con valores
        total = sum(sizes)
        legend_labels = [f'{label}: ${size:,.2f} ({size/total*100:.1f}%)' for label, size in zip(labels, sizes)]
        plt.legend(legend_labels, loc="best")
        
        # Convertir a base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data

    @staticmethod
    def generate_debt_breakdown_pie(user_id):
        """Generar gráfico de pastel del desglose de deudas"""
        debt_summary = ReportService.get_debt_summary(user_id)
        
        # Preparar datos
        labels = []
        sizes = []
        
        if debt_summary['credit_card_debt'] > 0:
            labels.append('Tarjetas de Crédito')
            sizes.append(debt_summary['credit_card_debt'])
        
        if debt_summary['account_debt'] > 0:
            labels.append('Cuentas de Deuda')
            sizes.append(debt_summary['account_debt'])
        
        if not sizes:
            return None
        
        # Colores para diferentes tipos de deuda
        colors = ['#ff6b6b', '#feca57', '#48dbfb', '#ff9ff3', '#54a0ff']
        
        plt.figure(figsize=(8, 8))
        plt.pie(sizes, labels=labels, colors=colors[:len(sizes)],
                autopct='%1.1f%%', shadow=True, startangle=45)
        plt.title('Desglose de Deudas por Tipo', fontsize=14, fontweight='bold')
        
        # Agregar leyenda con valores
        total = sum(sizes)
        legend_labels = [f'{label}: ${size:,.2f}' for label, size in zip(labels, sizes)]
        plt.legend(legend_labels, loc="best")
        
        # Convertir a base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data

    @staticmethod
    def generate_monthly_flow_chart(user_id, year, month):
        """Generar gráfico de flujo mensual (ingresos vs gastos vs ahorro)"""
        monthly_summary = ReportService.get_monthly_summary(user_id, year, month)
        
        categories = ['Ingresos', 'Gastos', 'Ahorro/Pérdida']
        values = [
            monthly_summary['total_income'],
            monthly_summary['total_expenses'],
            monthly_summary['net_income']
        ]
        
        # Colores
        colors = ['#28a745', '#dc3545', '#17a2b8' if values[2] >= 0 else '#ffc107']
        
        plt.figure(figsize=(10, 6))
        bars = plt.bar(categories, values, color=colors, alpha=0.8)
        
        # Agregar valores sobre las barras
        for bar, value in zip(bars, values):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + (max(values) * 0.01),
                    f'${value:,.2f}', ha='center', va='bottom', fontweight='bold')
        
        plt.title(f'Flujo Financiero - {datetime(year, month, 1).strftime("%B %Y")}', 
                 fontsize=14, fontweight='bold')
        plt.ylabel('Monto ($)')
        plt.grid(True, alpha=0.3, axis='y')
        
        # Ajustar límites del eje Y
        max_val = max(abs(min(values)), max(values))
        plt.ylim(-max_val * 0.1, max_val * 1.2)
        
        # Convertir a base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data

    @staticmethod
    def generate_account_balances_chart(user_id):
        """Generar gráfico de barras de balances por cuenta"""
        # Obtener todas las cuentas activas
        accounts = Account.query.filter_by(user_id=user_id, is_active=True).all()
        
        if not accounts:
            return None
        
        # Separar cuentas normales y de deuda
        normal_accounts = [acc for acc in accounts if not acc.is_debt_account]
        debt_accounts = [acc for acc in accounts if acc.is_debt_account]
        
        account_names = []
        balances = []
        colors = []
        
        # Agregar cuentas normales (activos)
        for acc in normal_accounts:
            account_names.append(acc.name)
            balances.append(acc.balance)
            colors.append('#28a745')  # Verde para activos
        
        # Agregar cuentas de deuda (pasivos, mostrar como negativos)
        for acc in debt_accounts:
            account_names.append(f"{acc.name} (Deuda)")
            balances.append(-abs(acc.balance))  # Mostrar como negativo
            colors.append('#dc3545')  # Rojo para deudas
        
        plt.figure(figsize=(12, 8))
        bars = plt.barh(account_names, balances, color=colors, alpha=0.8)
        
        # Agregar valores en las barras
        for i, (bar, balance) in enumerate(zip(bars, balances)):
            width = bar.get_width()
            label_x = width + (max(balances) * 0.01) if width >= 0 else width - (max(balances) * 0.01)
            ha = 'left' if width >= 0 else 'right'
            plt.text(label_x, bar.get_y() + bar.get_height()/2,
                    f'${abs(balance):,.2f}', ha=ha, va='center', fontweight='bold')
        
        plt.title('Balance por Cuenta', fontsize=14, fontweight='bold')
        plt.xlabel('Balance ($)')
        plt.grid(True, alpha=0.3, axis='x')
        
        # Línea vertical en x=0
        plt.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        
        # Ajustar espaciado
        plt.tight_layout()
        
        # Convertir a base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data

    @staticmethod
    def get_income_by_account_summary(user_id, year=None, month=None):
        """Obtener resumen de ingresos por cuenta"""
        # Si no se especifica año/mes, usar el actual
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month
            
        # Fechas del período
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Obtener todas las cuentas activas del usuario (no de deuda)
        accounts = Account.query.filter_by(
            user_id=user_id, 
            is_active=True,
            is_debt_account=False
        ).all()
        
        income_by_account = {}
        total_income = 0
        
        for account in accounts:
            # Obtener ingresos del período para esta cuenta
            income_transactions = Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.account_id == account.id,
                Transaction.transaction_type == 'income',
                # Excluir abonos que provienen de pagos a tarjetas (no son ingreso real)
                Transaction.credit_card_id.is_(None),
                Transaction.date >= start_date,
                Transaction.date < end_date
            ).all()
            
            account_income = sum(t.amount for t in income_transactions)
            
            if account_income > 0:
                income_by_account[account.name] = {
                    'account_id': account.id,
                    'account_name': account.name,
                    'total_income': account_income,
                    'transaction_count': len(income_transactions),
                    'transactions': income_transactions,
                    'current_balance': account.balance
                }
                total_income += account_income
        
        # Calcular porcentajes
        for account_data in income_by_account.values():
            if total_income > 0:
                account_data['percentage'] = (account_data['total_income'] / total_income) * 100
            else:
                account_data['percentage'] = 0
        
        return {
            'income_by_account': income_by_account,
            'total_income': total_income,
            'account_count': len(income_by_account),
            'period': f"{datetime(year, month, 1).strftime('%B %Y')}"
        }

    @staticmethod
    def generate_income_by_account_pie(user_id, year=None, month=None):
        """Generar gráfico de pastel de ingresos por cuenta"""
        income_data = ReportService.get_income_by_account_summary(user_id, year, month)
        
        if not income_data['income_by_account']:
            return None
        
        # Preparar datos para el gráfico
        labels = []
        sizes = []
        colors = ['#28a745', '#17a2b8', '#ffc107', '#dc3545', '#6f42c1', '#fd7e14', '#20c997', '#e83e8c']
        
        for account_name, data in income_data['income_by_account'].items():
            labels.append(account_name)
            sizes.append(data['total_income'])
        
        plt.figure(figsize=(10, 8))
        wedges, texts, autotexts = plt.pie(sizes, labels=labels, colors=colors[:len(sizes)],
                                          autopct='%1.1f%%', shadow=True, startangle=45)
        
        # Mejorar el texto
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        plt.title(f'Distribución de Ingresos por Cuenta\n{income_data["period"]}', 
                 fontsize=14, fontweight='bold')
        
        # Agregar leyenda con valores
        legend_labels = [f'{label}: ${size:,.2f}' for label, size in zip(labels, sizes)]
        plt.legend(legend_labels, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        
        # Convertir a base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data

    @staticmethod
    def generate_income_by_account_bar(user_id, year=None, month=None):
        """Generar gráfico de barras de ingresos por cuenta"""
        income_data = ReportService.get_income_by_account_summary(user_id, year, month)
        
        if not income_data['income_by_account']:
            return None
        
        # Preparar datos
        account_names = list(income_data['income_by_account'].keys())
        income_amounts = [data['total_income'] for data in income_data['income_by_account'].values()]
        
        # Ordenar por monto descendente
        sorted_data = sorted(zip(account_names, income_amounts), key=lambda x: x[1], reverse=True)
        account_names, income_amounts = zip(*sorted_data)
        
        plt.figure(figsize=(12, 8))
        bars = plt.bar(account_names, income_amounts, color='#28a745', alpha=0.8)
        
        # Agregar valores sobre las barras
        for bar, amount in zip(bars, income_amounts):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + (max(income_amounts) * 0.01),
                    f'${amount:,.2f}', ha='center', va='bottom', fontweight='bold')
        
        plt.title(f'Ingresos por Cuenta - {income_data["period"]}', 
                 fontsize=14, fontweight='bold')
        plt.ylabel('Ingresos ($)')
        plt.xlabel('Cuentas')
        plt.xticks(rotation=45, ha='right')
        plt.grid(True, alpha=0.3, axis='y')
        
        # Ajustar layout
        plt.tight_layout()
        
        # Convertir a base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()
        
        return img_data
