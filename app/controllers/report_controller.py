from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.services.report_service import ReportService
from app.services.payment_reminder_service import PaymentReminderService
from datetime import datetime

class ReportController:
    
    @staticmethod
    @login_required
    def monthly_report():
        """Mostrar reporte mensual"""
        # Obtener año y mes de los parámetros o usar actual
        year = request.args.get('year', datetime.now().year, type=int)
        month = request.args.get('month', datetime.now().month, type=int)
        
        # Obtener datos del reporte
        monthly_summary = ReportService.get_monthly_summary(current_user.id, year, month)
        debt_summary = ReportService.get_debt_summary(current_user.id)
        net_worth = ReportService.get_net_worth(current_user.id)
        
        # Generar gráficos
        expense_chart = ReportService.generate_expense_chart(current_user.id, year, month)
        assets_liabilities_pie = ReportService.generate_assets_liabilities_pie(current_user.id)
        debt_breakdown_pie = ReportService.generate_debt_breakdown_pie(current_user.id)
        monthly_flow_chart = ReportService.generate_monthly_flow_chart(current_user.id, year, month)
        account_balances_chart = ReportService.generate_account_balances_chart(current_user.id)
        income_expense_trend = ReportService.generate_income_expense_trend(current_user.id, year)
        
        # Obtener recordatorios pendientes
        pending_reminders = PaymentReminderService.get_pending_reminders(current_user.id)
        overdue_reminders = PaymentReminderService.get_overdue_reminders(current_user.id)
        
        return render_template('reports/monthly.html',
                             year=year,
                             month=month,
                             month_name=datetime(year, month, 1).strftime('%B'),
                             monthly_summary=monthly_summary,
                             debt_summary=debt_summary,
                             net_worth=net_worth,
                             expense_chart=expense_chart,
                             assets_liabilities_pie=assets_liabilities_pie,
                             debt_breakdown_pie=debt_breakdown_pie,
                             monthly_flow_chart=monthly_flow_chart,
                             account_balances_chart=account_balances_chart,
                             income_expense_trend=income_expense_trend,
                             pending_reminders=pending_reminders,
                             overdue_reminders=overdue_reminders)
    
    @staticmethod
    @login_required
    def income_by_account_report():
        """Mostrar reporte de ingresos por cuenta"""
        # Obtener año y mes de los parámetros o usar actual
        year = request.args.get('year', datetime.now().year, type=int)
        month = request.args.get('month', datetime.now().month, type=int)
        
        # Obtener datos del reporte
        income_summary = ReportService.get_income_by_account_summary(current_user.id, year, month)
        
        # Generar gráficos
        income_pie_chart = ReportService.generate_income_by_account_pie(current_user.id, year, month)
        income_bar_chart = ReportService.generate_income_by_account_bar(current_user.id, year, month)
        
        return render_template('reports/income_by_account.html',
                             year=year,
                             month=month,
                             month_name=datetime(year, month, 1).strftime('%B'),
                             income_summary=income_summary,
                             income_pie_chart=income_pie_chart,
                             income_bar_chart=income_bar_chart)
    
    @staticmethod
    @login_required
    def quarterly_report():
        """Mostrar reporte trimestral"""
        # Obtener año y trimestre de los parámetros o usar actual
        year = request.args.get('year', datetime.now().year, type=int)
        quarter = request.args.get('quarter', ((datetime.now().month - 1) // 3) + 1, type=int)
        
        # Obtener datos del reporte trimestral
        quarterly_data = ReportService.get_quarterly_report(current_user.id, year, quarter)
        debt_summary = ReportService.get_debt_summary(current_user.id)
        net_worth = ReportService.get_net_worth(current_user.id)
        
        # Generar gráfico de tendencia anual
        trend_chart = ReportService.generate_income_expense_trend(current_user.id, year)
        
        # Calcular algunas métricas adicionales
        avg_savings_rate = 0
        if quarterly_data['avg_monthly_income'] > 0:
            avg_savings_rate = ((quarterly_data['avg_monthly_income'] - quarterly_data['avg_monthly_expenses']) / quarterly_data['avg_monthly_income']) * 100
        
        quarter_names = {
            1: 'Primer Trimestre (Ene-Mar)',
            2: 'Segundo Trimestre (Abr-Jun)',
            3: 'Tercer Trimestre (Jul-Sep)',
            4: 'Cuarto Trimestre (Oct-Dic)'
        }
        
        return render_template('reports/quarterly.html',
                             year=year,
                             quarter=quarter,
                             quarter_name=quarter_names.get(quarter, f'Trimestre {quarter}'),
                             quarterly_data=quarterly_data,
                             debt_summary=debt_summary,
                             net_worth=net_worth,
                             trend_chart=trend_chart,
                             avg_savings_rate=avg_savings_rate)
    
    @staticmethod
    @login_required
    def annual_summary():
        """Mostrar resumen anual"""
        year = request.args.get('year', datetime.now().year, type=int)
        
        # Obtener datos de todos los trimestres
        annual_data = {
            'quarters': [],
            'total_income': 0,
            'total_expenses': 0,
            'net_income': 0
        }
        
        for quarter in range(1, 5):
            quarterly_data = ReportService.get_quarterly_report(current_user.id, year, quarter)
            annual_data['quarters'].append(quarterly_data)
            annual_data['total_income'] += quarterly_data['total_income']
            annual_data['total_expenses'] += quarterly_data['total_expenses']
        
        annual_data['net_income'] = annual_data['total_income'] - annual_data['total_expenses']
        
        # Promedios mensuales
        annual_data['avg_monthly_income'] = annual_data['total_income'] / 12
        annual_data['avg_monthly_expenses'] = annual_data['total_expenses'] / 12
        
        # Tasa de ahorro anual
        savings_rate = 0
        if annual_data['total_income'] > 0:
            savings_rate = (annual_data['net_income'] / annual_data['total_income']) * 100
        
        # Datos adicionales
        debt_summary = ReportService.get_debt_summary(current_user.id)
        net_worth = ReportService.get_net_worth(current_user.id)
        trend_chart = ReportService.generate_income_expense_trend(current_user.id, year)
        
        return render_template('reports/annual.html',
                             year=year,
                             annual_data=annual_data,
                             savings_rate=savings_rate,
                             debt_summary=debt_summary,
                             net_worth=net_worth,
                             trend_chart=trend_chart)
    
    @staticmethod
    @login_required
    def debt_analysis():
        """Análisis detallado de deudas"""
        debt_summary = ReportService.get_debt_summary(current_user.id)
        
        # Análisis de utilización por tarjeta
        from app.models.credit_card import CreditCard
        credit_cards = CreditCard.query.filter_by(user_id=current_user.id, is_active=True).all()
        
        card_analysis = []
        for card in credit_cards:
            utilization = card.get_utilization_percentage()
            status = 'excellent' if utilization < 10 else 'good' if utilization < 30 else 'warning' if utilization < 70 else 'danger'
            
            card_analysis.append({
                'card': card,
                'utilization': utilization,
                'status': status,
                'interest_per_month': card.current_balance * (card.interest_rate / 100) if card.interest_rate > 0 else 0
            })
        
        # Proyección de pagos
        total_monthly_interest = sum(analysis['interest_per_month'] for analysis in card_analysis)
        
        # Recomendaciones
        recommendations = []
        if debt_summary['utilization_percentage'] > 30:
            recommendations.append("Tu utilización de crédito está alta (>30%). Considera pagar más del mínimo para reducirla.")
        
        if len([c for c in card_analysis if c['utilization'] > 70]) > 0:
            recommendations.append("Tienes tarjetas con alta utilización (>70%). Prioriza pagarlas para mejorar tu score crediticio.")
        
        if total_monthly_interest > 0:
            recommendations.append(f"Estás pagando aproximadamente ${total_monthly_interest:.2f} mensuales en intereses.")
        
        return render_template('reports/debt_analysis.html',
                             debt_summary=debt_summary,
                             card_analysis=card_analysis,
                             total_monthly_interest=total_monthly_interest,
                             recommendations=recommendations)
    
    @staticmethod
    @login_required
    def export_data():
        """Exportar datos en formato JSON"""
        year = request.args.get('year', datetime.now().year, type=int)
        
        # Recopilar todos los datos
        export_data = {
            'user_info': {
                'name': current_user.get_full_name(),
                'monthly_income': current_user.monthly_income
            },
            'annual_summary': {},
            'quarterly_reports': {},
            'debt_summary': ReportService.get_debt_summary(current_user.id),
            'net_worth': ReportService.get_net_worth(current_user.id),
            'export_date': datetime.now().isoformat()
        }
        
        # Datos anuales
        for quarter in range(1, 5):
            quarterly_data = ReportService.get_quarterly_report(current_user.id, year, quarter)
            export_data['quarterly_reports'][f'Q{quarter}'] = quarterly_data
        
        return jsonify(export_data)
