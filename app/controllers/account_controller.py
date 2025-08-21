from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.account import Account
from app.models.transaction import Transaction
from app import db
from datetime import datetime

class AccountController:
    
    @staticmethod
    @login_required
    def list_accounts():
        """Listar todas las cuentas del usuario"""
        accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
        total_balance = sum(account.balance for account in accounts)
        
        return render_template('accounts/list.html', 
                             accounts=accounts, 
                             total_balance=total_balance)
    
    @staticmethod
    @login_required
    def create_account():
        """Crear nueva cuenta"""
        if request.method == 'POST':
            try:
                name = request.form.get('name')
                account_type = request.form.get('account_type')
                # Soportar tanto 'initial_balance' como 'balance' desde el formulario
                _ib_raw = request.form.get('initial_balance')
                if _ib_raw is None or _ib_raw == '':
                    _ib_raw = request.form.get('balance', 0)
                try:
                    initial_balance = float(_ib_raw) if _ib_raw not in (None, '') else 0.0
                except ValueError:
                    initial_balance = 0.0
                bank_name = request.form.get('bank_name')
                account_number = request.form.get('account_number')
                
                if not name or not account_type:
                    flash('Nombre y tipo de cuenta son obligatorios.', 'error')
                    return render_template('accounts/create.html')
                
                # Crear nueva cuenta
                account = Account(
                    user_id=current_user.id,
                    name=name,
                    account_type=account_type,
                    balance=initial_balance,
                    bank_name=bank_name,
                    account_number=account_number
                )
                
                # Campos para cuentas de inversión y ahorro
                if account_type in ['savings', 'investment']:
                    generates_interest = request.form.get('generates_interest') == 'on'
                    interest_rate = float(request.form.get('interest_rate', 0))
                    investment_type = request.form.get('investment_type')
                    compound_frequency = request.form.get('compound_frequency', 'monthly')
                    
                    account.generates_interest = generates_interest
                    account.interest_rate = interest_rate
                    account.investment_type = investment_type
                    account.compound_frequency = compound_frequency
                    
                    if generates_interest:
                        account.last_interest_calculation = datetime.utcnow()
                
                db.session.add(account)
                db.session.flush()  # Esto asigna el ID sin hacer commit
                
                # Si hay balance inicial, crear transacción
                if initial_balance != 0:
                    transaction = Transaction(
                        user_id=current_user.id,
                        account_id=account.id,
                        amount=abs(initial_balance),
                        description="Saldo inicial",
                        category="other",
                        transaction_type="income" if initial_balance > 0 else "expense",
                        date=datetime.now().date()
                    )
                    db.session.add(transaction)
                
                db.session.commit()
                flash('Cuenta creada exitosamente.', 'success')
                return redirect(url_for('main.accounts'))
                
            except ValueError:
                flash('El saldo inicial debe ser un número válido.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Error al crear la cuenta.', 'error')
        
        account_types = [
            ('checking', 'Cuenta Corriente'),
            ('savings', 'Cuenta de Ahorros'),
            ('investment', 'Inversión')
        ]
        
        return render_template('accounts/create.html', account_types=account_types)
    
    @staticmethod
    @login_required
    def edit_account(account_id):
        """Editar cuenta existente"""
        account = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
        
        if request.method == 'POST':
            try:
                # Obtener el balance anterior para calcular diferencia
                old_balance = account.balance
                # Soportar 'initial_balance' o 'balance' en edición también
                _nb_raw = request.form.get('initial_balance')
                if _nb_raw is None or _nb_raw == '':
                    _nb_raw = request.form.get('balance', 0)
                try:
                    new_balance = float(_nb_raw) if _nb_raw not in (None, '') else 0.0
                except ValueError:
                    new_balance = old_balance
                
                account.name = request.form.get('name')
                account.account_type = request.form.get('account_type')
                account.bank_name = request.form.get('bank_name')
                account.account_number = request.form.get('account_number')
                account.balance = new_balance
                account.is_active = bool(request.form.get('is_active'))
                
                # Actualizar campos de inversión
                if account.account_type in ['savings', 'investment']:
                    generates_interest = request.form.get('generates_interest') == 'on'
                    interest_rate = float(request.form.get('interest_rate', 0))
                    investment_type = request.form.get('investment_type')
                    compound_frequency = request.form.get('compound_frequency', 'monthly')
                    
                    account.generates_interest = generates_interest
                    account.interest_rate = interest_rate
                    account.investment_type = investment_type
                    account.compound_frequency = compound_frequency
                else:
                    # Limpiar campos de inversión para otros tipos de cuenta
                    account.generates_interest = False
                    account.interest_rate = 0.0
                    account.investment_type = None
                    account.compound_frequency = 'monthly'
                
                if not account.name or not account.account_type:
                    flash('Nombre y tipo de cuenta son obligatorios.', 'error')
                    return render_template('accounts/edit.html', account=account)
                
                # Si cambió el balance, crear una transacción de ajuste
                balance_difference = new_balance - old_balance
                if balance_difference != 0:
                    transaction = Transaction(
                        user_id=current_user.id,
                        account_id=account.id,
                        amount=abs(balance_difference),
                        description=f'Ajuste de saldo - Edición de cuenta',
                        category='other',
                        transaction_type='income' if balance_difference > 0 else 'expense',
                        date=datetime.now().date()
                    )
                    db.session.add(transaction)
                    
                    # Actualizar balance basado en las transacciones
                    db.session.flush()  # Para asegurar que la transacción se agrega
                    account.update_balance()
                else:
                    # Solo actualizar el balance directamente si no hay cambio en saldo
                    account.balance = new_balance
                
                db.session.commit()
                flash('Cuenta actualizada exitosamente.', 'success')
                return redirect(url_for('main.accounts'))
                
            except Exception as e:
                db.session.rollback()
                flash('Error al actualizar la cuenta.', 'error')
        
        account_types = [
            ('checking', 'Cuenta Corriente'),
            ('savings', 'Cuenta de Ahorros'),
            ('investment', 'Inversión')
        ]
        
        return render_template('accounts/edit.html', account=account, account_types=account_types)
    
    @staticmethod
    @login_required
    def delete_account(account_id):
        """Eliminar cuenta (desactivar)"""
        account = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
        
        try:
            # En lugar de eliminar, desactivar la cuenta
            account.is_active = False
            db.session.commit()
            flash('Cuenta eliminada exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error al eliminar la cuenta.', 'error')
        
        return redirect(url_for('main.accounts'))
    
    @staticmethod
    @login_required
    def account_details(account_id):
        """Ver detalles de una cuenta específica"""
        account = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
        
        # Obtener transacciones recientes
        recent_transactions = Transaction.query.filter_by(
            account_id=account.id
        ).order_by(Transaction.date.desc()).limit(20).all()
        
        # Calcular estadísticas del mes actual
        current_date = datetime.now()
        month_start = datetime(current_date.year, current_date.month, 1)
        
        monthly_transactions = Transaction.query.filter(
            Transaction.account_id == account.id,
            Transaction.date >= month_start
        ).all()
        
        monthly_income = sum(t.amount for t in monthly_transactions if t.transaction_type == 'income')
        monthly_expenses = sum(t.amount for t in monthly_transactions if t.transaction_type == 'expense')
        
        return render_template('accounts/details.html',
                             account=account,
                             recent_transactions=recent_transactions,
                             monthly_income=monthly_income,
                             monthly_expenses=monthly_expenses)
    
    @staticmethod
    @login_required
    def get_account_balance(account_id):
        """API endpoint para obtener balance de cuenta"""
        account = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
        
        if account:
            return jsonify({
                'success': True,
                'balance': account.balance,
                'account_name': account.name
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Cuenta no encontrada'
            }), 404
