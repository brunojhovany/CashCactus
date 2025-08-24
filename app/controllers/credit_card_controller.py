from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.credit_card import CreditCard
from app.models.transaction import Transaction
from app.services.payment_reminder_service import PaymentReminderService
from app import db
from datetime import datetime

class CreditCardController:
    
    @staticmethod
    @login_required
    def list_credit_cards():
        """Listar tarjetas de crédito del usuario"""
        credit_cards = CreditCard.query.filter_by(user_id=current_user.id, is_active=True).all()
        
        # Calcular totales
        total_debt = sum(card.current_balance for card in credit_cards)
        total_credit_limit = sum(card.credit_limit for card in credit_cards)
        total_available_credit = total_credit_limit - total_debt
        
        # Próximos vencimientos
        upcoming_payments = []
        for card in credit_cards:
            if card.current_balance > 0:
                upcoming_payments.append({
                    'card': card,
                    'days_until_due': card.get_days_until_due()
                })
        
        upcoming_payments.sort(key=lambda x: x['days_until_due'])
        
        return render_template('credit_cards/list.html',
                             credit_cards=credit_cards,
                             total_debt=total_debt,
                             total_credit_limit=total_credit_limit,
                             total_available_credit=total_available_credit,
                             upcoming_payments=upcoming_payments)
    
    @staticmethod
    @login_required
    def create_credit_card():
        """Crear nueva tarjeta de crédito"""
        if request.method == 'POST':
            try:
                name = request.form.get('name')
                bank_name = request.form.get('bank_name')
                last_four_digits = request.form.get('last_four_digits')
                credit_limit = float(request.form.get('credit_limit'))
                current_balance = float(request.form.get('current_balance', 0))
                due_date = int(request.form.get('due_date'))
                closing_date = int(request.form.get('closing_date'))
                interest_rate = float(request.form.get('interest_rate', 0))
                is_active = bool(request.form.get('is_active'))
                
                # Validaciones
                if not name or not credit_limit:
                    flash('Nombre y límite de crédito son obligatorios.', 'error')
                    return render_template('credit_cards/create.html')
                
                if credit_limit <= 0:
                    flash('El límite de crédito debe ser mayor a 0.', 'error')
                    return render_template('credit_cards/create.html')
                
                if current_balance > credit_limit:
                    flash('El saldo actual no puede ser mayor al límite de crédito.', 'error')
                    return render_template('credit_cards/create.html')
                
                if not (1 <= due_date <= 31) or not (1 <= closing_date <= 31):
                    flash('Las fechas de vencimiento y corte deben estar entre 1 y 31.', 'error')
                    return render_template('credit_cards/create.html')
                
                # Crear nueva tarjeta
                credit_card = CreditCard(
                    user_id=current_user.id,
                    name=name,
                    bank_name=bank_name,
                    last_four_digits=last_four_digits,
                    credit_limit=credit_limit,
                    current_balance=current_balance,
                    due_date=due_date,
                    closing_date=closing_date,
                    interest_rate=interest_rate,
                    is_active=is_active
                )
                
                credit_card.update_minimum_payment()
                db.session.add(credit_card)
                db.session.commit()
                
                # Crear recordatorio de pago
                PaymentReminderService.create_credit_card_reminders(current_user.id)
                
                flash('Tarjeta de crédito creada exitosamente.', 'success')
                return redirect(url_for('main.credit_cards'))
                
            except ValueError:
                flash('Por favor, verifica que todos los números sean válidos.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Error al crear la tarjeta de crédito.', 'error')
        
        return render_template('credit_cards/create.html')
    
    @staticmethod
    @login_required
    def edit_credit_card(card_id):
        """Editar tarjeta de crédito existente"""
        credit_card = CreditCard.query.filter_by(id=card_id, user_id=current_user.id).first_or_404()
        
        if request.method == 'POST':
            try:
                credit_card.name = request.form.get('name')
                credit_card.bank_name = request.form.get('bank_name')
                credit_card.last_four_digits = request.form.get('last_four_digits')
                credit_card.credit_limit = float(request.form.get('credit_limit'))
                credit_card.current_balance = float(request.form.get('current_balance'))
                credit_card.due_date = int(request.form.get('due_date'))
                credit_card.closing_date = int(request.form.get('closing_date'))
                credit_card.interest_rate = float(request.form.get('interest_rate', 0))
                credit_card.is_active = bool(request.form.get('is_active'))
                
                # Validaciones
                if credit_card.current_balance > credit_card.credit_limit:
                    flash('El saldo actual no puede ser mayor al límite de crédito.', 'error')
                    return render_template('credit_cards/edit.html', credit_card=credit_card)
                
                credit_card.update_minimum_payment()
                db.session.commit()
                flash('Tarjeta de crédito actualizada exitosamente.', 'success')
                return redirect(url_for('main.credit_cards'))
                
            except ValueError:
                flash('Por favor, verifica que todos los números sean válidos.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Error al actualizar la tarjeta de crédito.', 'error')
        
        return render_template('credit_cards/edit.html', credit_card=credit_card)
    
    @staticmethod
    @login_required
    def delete_credit_card(card_id):
        """Eliminar tarjeta de crédito (desactivar)"""
        credit_card = CreditCard.query.filter_by(id=card_id, user_id=current_user.id).first_or_404()
        
        try:
            # En lugar de eliminar, desactivar la tarjeta
            credit_card.is_active = False
            db.session.commit()
            flash('Tarjeta de crédito eliminada exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error al eliminar la tarjeta de crédito.', 'error')
        
        return redirect(url_for('main.credit_cards'))
    
    @staticmethod
    @login_required
    def card_details(card_id):
        """Ver detalles de una tarjeta específica"""
        credit_card = CreditCard.query.filter_by(id=card_id, user_id=current_user.id).first_or_404()
        
        # Obtener transacciones recientes
        recent_transactions = Transaction.query.filter(
            Transaction.credit_card_id == card_id,
            Transaction.user_id == current_user.id
        ).order_by(Transaction.date.desc()).limit(20).all()
        
        # Calcular estadísticas del mes actual
        current_date = datetime.now()
        month_start = datetime(current_date.year, current_date.month, 1)
        
        monthly_transactions = Transaction.query.filter(
            Transaction.credit_card_id == card_id,
            Transaction.user_id == current_user.id,
            Transaction.date >= month_start
        ).all()
        
        monthly_purchases = sum(t.amount for t in monthly_transactions if t.transaction_type == 'expense')
        monthly_payments = sum(t.amount for t in monthly_transactions if t.transaction_type == 'income')
        
        return render_template('credit_cards/details.html',
                             credit_card=credit_card,
                             recent_transactions=recent_transactions,
                             monthly_purchases=monthly_purchases,
                             monthly_payments=monthly_payments)
    
    @staticmethod
    @login_required
    def make_payment(card_id):
        """Realizar pago a tarjeta de crédito"""
        credit_card = CreditCard.query.filter_by(id=card_id, user_id=current_user.id).first_or_404()
        
        if request.method == 'POST':
            try:
                amount = float(request.form.get('amount'))
                account_id = request.form.get('account_id')
                description = request.form.get('description', f'Pago a {credit_card.name}')
                
                if amount <= 0:
                    flash('El monto del pago debe ser mayor a 0.', 'error')
                    return render_template('credit_cards/payment.html', 
                                         credit_card=credit_card, 
                                         accounts=current_user.accounts)
                
                if amount > credit_card.current_balance:
                    flash('El monto del pago no puede ser mayor al saldo actual.', 'error')
                    return render_template('credit_cards/payment.html', 
                                         credit_card=credit_card, 
                                         accounts=current_user.accounts)
                
                # Verificar fondos en cuenta si se especifica
                if account_id:
                    from app.models.account import Account
                    account = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
                    if not account or account.balance < amount:
                        flash('Fondos insuficientes en la cuenta seleccionada.', 'error')
                        return render_template('credit_cards/payment.html', 
                                             credit_card=credit_card, 
                                             accounts=current_user.accounts)
                    
                    # Descontar de la cuenta
                    account.balance -= amount
                    
                    # Crear transacción de egreso para la cuenta bancaria
                    account_transaction = Transaction(
                        user_id=current_user.id,
                        account_id=int(account_id),
                        amount=amount,
                        description=f"Pago a {credit_card.name}",
                        category='debt_payment',
                        transaction_type='expense'  # Para la cuenta es un gasto
                    )
                    db.session.add(account_transaction)
                
                # Crear transacción de ingreso para la tarjeta de crédito
                card_transaction = Transaction(
                    user_id=current_user.id,
                    credit_card_id=credit_card.id,
                    amount=amount,
                    description=description,
                    category='debt_payment',
                    transaction_type='income'  # Para la tarjeta es ingreso (pago)
                )
                
                # Actualizar saldo de tarjeta
                credit_card.current_balance -= amount
                credit_card.update_minimum_payment()
                
                db.session.add(card_transaction)
                db.session.commit()
                
                flash(f'Pago de ${amount:.2f} realizado exitosamente.', 'success')
                return redirect(url_for('main.card_details', card_id=card_id))
                
            except ValueError:
                flash('El monto debe ser un número válido.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Error al procesar el pago.', 'error')
        
        from app.models.account import Account
        accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
        
        return render_template('credit_cards/payment.html',
                             credit_card=credit_card,
                             accounts=accounts)
