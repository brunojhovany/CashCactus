from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.transaction import Transaction
from app.models.account import Account
from app.models.credit_card import CreditCard
from app.utils.security import (
    ensure_transaction_account_ownership,
    ensure_transaction_credit_card_ownership
)
from app import db
from datetime import datetime

def get_transaction_categories():
    """Obtener lista de categorías disponibles para transacciones"""
    return [
        ('food', 'Alimentación'),
        ('transport', 'Transporte'),
        ('entertainment', 'Entretenimiento'),
        ('utilities', 'Servicios'),
        ('healthcare', 'Salud'),
        ('shopping', 'Compras'),
        ('education', 'Educación'),
        ('travel', 'Viajes'),
        ('debt_payment', 'Pago de Deudas'),
        ('debt_interest', 'Interés de Deuda'),
        ('investment_income', 'Rendimiento de Inversión'),
        ('salary', 'Salario'),
        ('freelance', 'Trabajos Independientes'),
        ('investment', 'Inversiones'),
        ('other', 'Otros')
    ]

class TransactionController:
    
    @staticmethod
    @login_required
    def list_transactions():
        """Listar transacciones del usuario"""
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filtros
        account_id = request.args.get('account_id')
        category = request.args.get('category')
        transaction_type = request.args.get('transaction_type')
        
        query = Transaction.query.filter_by(user_id=current_user.id)
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        if category:
            query = query.filter_by(category=category)
        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)
        
        transactions = query.order_by(Transaction.date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Obtener cuentas para el filtro
        accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
        
        # Categorías disponibles
        categories = get_transaction_categories()
        
        return render_template('transactions/list.html',
                             transactions=transactions,
                             accounts=accounts,
                             categories=categories)
    
    @staticmethod
    @login_required
    def list_account_transactions(account_id):
        """Listar transacciones de una cuenta específica"""
        # Verificar que la cuenta pertenece al usuario
        account = Account.query.filter_by(
            id=account_id, 
            user_id=current_user.id
        ).first_or_404()
        
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filtros adicionales
        category = request.args.get('category')
        transaction_type = request.args.get('transaction_type')
        
        query = Transaction.query.filter_by(
            user_id=current_user.id,
            account_id=account_id
        )
        
        if category:
            query = query.filter_by(category=category)
        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)
        
        transactions = query.order_by(Transaction.date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Categorías disponibles
        categories = get_transaction_categories()
        
        return render_template('transactions/account_list.html',
                             transactions=transactions,
                             account=account,
                             categories=categories)
    
    @staticmethod
    @login_required
    def create_transaction():
        """Crear nueva transacción"""
        if request.method == 'POST':
            try:
                transaction_type = request.form.get('transaction_type')
                amount = float(request.form.get('amount'))
                description = request.form.get('description')
                category = request.form.get('category')
                account_id = request.form.get('account_id')
                credit_card_id = request.form.get('credit_card_id')
                date = request.form.get('date')
                notes = request.form.get('notes')
                
                # Validaciones
                if not all([transaction_type, amount, description, category]):
                    flash('Todos los campos obligatorios deben ser completados.', 'error')
                    return redirect(url_for('main.create_transaction'))
                
                if amount <= 0:
                    flash('El monto debe ser mayor a 0.', 'error')
                    return redirect(url_for('main.create_transaction'))
                
                # Parsear fecha
                transaction_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
                
                # Verificar que se haya seleccionado cuenta o tarjeta
                if not account_id and not credit_card_id:
                    flash('Debes seleccionar una cuenta o tarjeta de crédito.', 'error')
                    return redirect(url_for('main.create_transaction'))
                
                # Crear transacción
                # Validar propiedad de cuenta / tarjeta
                _account = ensure_transaction_account_ownership(int(account_id)) if account_id else None
                _card = ensure_transaction_credit_card_ownership(int(credit_card_id)) if credit_card_id else None

                transaction = Transaction(
                    user_id=current_user.id,
                    account_id=_account.id if _account else None,
                    credit_card_id=_card.id if _card else None,
                    amount=amount,
                    description=description,
                    category=category,
                    transaction_type=transaction_type,
                    date=transaction_date,
                    notes=notes
                )
                
                # Para pagos de deudas a terceros
                if category == 'debt_payment':
                    creditor_name = request.form.get('creditor_name')
                    transaction.creditor_name = creditor_name
                    transaction.is_debt_payment = True
                
                db.session.add(transaction)
                
                # Actualizar balance de cuenta usando el método update_balance
                if _account:
                    _account.update_balance()
                
                # Actualizar balance de tarjeta de crédito
                elif _card:
                    if transaction_type == 'expense':
                        _card.current_balance += amount
                    elif transaction_type == 'income':  # Pago de tarjeta
                        _card.current_balance -= amount
                        _card.update_minimum_payment()
                
                db.session.commit()
                flash('Transacción registrada exitosamente.', 'success')
                return redirect(url_for('main.transactions'))
                
            except ValueError:
                flash('El monto debe ser un número válido.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Error al crear la transacción.', 'error')
        
        # Obtener cuentas y tarjetas para el formulario
        accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
        credit_cards = CreditCard.query.filter_by(user_id=current_user.id, is_active=True).all()
        
        # Obtener account_id desde la URL si viene de una cuenta específica
        preselected_account_id = request.args.get('account_id')
        
        categories = get_transaction_categories()
        
        return render_template('transactions/create.html',
                             accounts=accounts,
                             credit_cards=credit_cards,
                             categories=categories,
                             current_date=datetime.now().strftime('%Y-%m-%d'),
                             preselected_account_id=preselected_account_id)
    
    @staticmethod
    @login_required
    def edit_transaction(transaction_id):
        """Editar transacción existente"""
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()

        if request.method == 'POST':
            try:
                # Guardar información anterior para recalcular balances
                old_account_id = transaction.account_id
                old_credit_card_id = transaction.credit_card_id
                old_amount = transaction.amount
                old_type = transaction.transaction_type

                # Actualizar transacción (validando pertenencia de nuevos recursos)
                new_account_id = request.form.get('account_id')
                new_card_id = request.form.get('credit_card_id')

                transaction.transaction_type = request.form.get('transaction_type')
                transaction.amount = float(request.form.get('amount'))
                transaction.description = request.form.get('description')
                transaction.category = request.form.get('category')
                transaction.account_id = ensure_transaction_account_ownership(int(new_account_id)).id if new_account_id else None
                transaction.credit_card_id = ensure_transaction_credit_card_ownership(int(new_card_id)).id if new_card_id else None
                transaction.notes = request.form.get('notes')

                date = request.form.get('date')
                if date:
                    transaction.date = datetime.strptime(date, '%Y-%m-%d')

                db.session.commit()

                # Recalcular balances para todas las cuentas afectadas
                affected_accounts = set()
                if old_account_id:
                    affected_accounts.add(old_account_id)
                if transaction.account_id:
                    affected_accounts.add(transaction.account_id)

                for acc_id in affected_accounts:
                    account = Account.query.get(acc_id)
                    if account and account.user_id == current_user.id:
                        account.update_balance()

                # Manejar tarjetas de crédito
                if old_credit_card_id and old_credit_card_id != transaction.credit_card_id:
                    old_card = CreditCard.query.get(old_credit_card_id)
                    if old_card and old_card.user_id == current_user.id:
                        if old_type == 'expense':
                            old_card.current_balance -= old_amount
                        elif old_type == 'income':
                            old_card.current_balance += old_amount
                        old_card.update_minimum_payment()

                if transaction.credit_card_id:
                    new_card = CreditCard.query.get(transaction.credit_card_id)
                    if new_card and new_card.user_id == current_user.id:
                        if transaction.transaction_type == 'expense':
                            new_card.current_balance += transaction.amount
                        elif transaction.transaction_type == 'income':
                            new_card.current_balance -= transaction.amount
                            new_card.update_minimum_payment()

                db.session.commit()
                flash('Transacción actualizada exitosamente.', 'success')
                return redirect(url_for('main.transactions'))

            except Exception:
                db.session.rollback()
                flash('Error al actualizar la transacción.', 'error')

        accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
        credit_cards = CreditCard.query.filter_by(user_id=current_user.id, is_active=True).all()
        categories = get_transaction_categories()

        return render_template('transactions/edit.html',
                               transaction=transaction,
                               accounts=accounts,
                               credit_cards=credit_cards,
                               categories=categories)
    
    @staticmethod
    @login_required
    def delete_transaction(transaction_id):
        """Eliminar transacción con lógica en cascada para actualizar balances"""
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()

        try:
            # Usar el nuevo método que maneja automáticamente todas las actualizaciones
            transaction.delete_with_cascade_update()

            db.session.commit()
            flash('Transacción eliminada exitosamente. Balances actualizados automáticamente.', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar la transacción: {str(e)}', 'error')

        return redirect(url_for('main.transactions'))
