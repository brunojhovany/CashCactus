from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.account import Account
from app.models.transaction import Transaction
from app import db
from datetime import datetime

class DebtController:
    
    @staticmethod
    @login_required
    def list_debt_accounts():
        """Listar todas las cuentas de deuda del usuario"""
        debt_accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_debt_account=True,
            is_active=True
        ).all()
        
        # Calcular información adicional para cada deuda
        debt_info = []
        for account in debt_accounts:
            info = {
                'account': account,
                'current_debt': abs(account.balance),  # Para deudas, el balance representa lo que se debe
                'monthly_interest': account.calculate_monthly_interest(),
                'next_payment_due': account.get_next_payment_due_date(),
                'is_overdue': account.is_payment_overdue()
            }
            debt_info.append(info)
        
        return render_template('debts/list.html', debt_accounts=debt_info)
    
    @staticmethod
    @login_required
    def create_debt_account():
        """Crear nueva cuenta de deuda"""
        if request.method == 'POST':
            try:
                name = request.form.get('name')
                creditor_name = request.form.get('creditor_name')
                original_amount = float(request.form.get('original_amount'))
                interest_rate = float(request.form.get('interest_rate', 0))
                minimum_payment = float(request.form.get('minimum_payment', 0))
                payment_due_day = int(request.form.get('payment_due_day', 1))
                notes = request.form.get('notes')
                
                # Validaciones
                if not all([name, creditor_name, original_amount]):
                    flash('Nombre, acreedor y monto original son obligatorios.', 'error')
                    return redirect(url_for('main.create_debt_account'))
                
                if original_amount <= 0:
                    flash('El monto original debe ser mayor a 0.', 'error')
                    return redirect(url_for('main.create_debt_account'))
                
                if not (1 <= payment_due_day <= 31):
                    flash('El día de vencimiento debe estar entre 1 y 31.', 'error')
                    return redirect(url_for('main.create_debt_account'))
                
                # Crear cuenta de deuda
                debt_account = Account(
                    user_id=current_user.id,
                    name=name,
                    account_type='debt',
                    balance=original_amount,  # Balance positivo para deudas (lo que se debe)
                    is_debt_account=True,
                    creditor_name=creditor_name,
                    original_debt_amount=original_amount,
                    interest_rate=interest_rate,
                    minimum_payment=minimum_payment,
                    payment_due_day=payment_due_day,
                    last_interest_calculation=datetime.utcnow(),
                    status='active'
                )
                
                db.session.add(debt_account)
                db.session.commit()
                
                flash('Cuenta de deuda creada exitosamente.', 'success')
                return redirect(url_for('main.debt_accounts'))
                
            except ValueError:
                flash('Por favor verifica que los números sean válidos.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Error al crear la cuenta de deuda.', 'error')
        
        return render_template('debts/create.html')
    
    @staticmethod
    @login_required
    def debt_detail(debt_id):
        """Ver detalles de una cuenta de deuda específica"""
        debt_account = Account.query.filter_by(
            id=debt_id,
            user_id=current_user.id,
            is_debt_account=True
        ).first_or_404()
        
        # Obtener transacciones de la deuda
        transactions = Transaction.query.filter_by(
            account_id=debt_id,
            user_id=current_user.id
        ).order_by(Transaction.date.desc()).limit(20).all()
        
        # Calcular proyección de pagos
        projection = debt_account.calculate_debt_projection(12)
        
        # Información adicional
        debt_info = {
            'current_debt': abs(debt_account.balance),  # Para deudas, el balance siempre representa lo que se debe
            'monthly_interest': debt_account.calculate_monthly_interest(),
            'next_payment_due': debt_account.get_next_payment_due_date(),
            'is_overdue': debt_account.is_payment_overdue(),
            'total_paid': (debt_account.original_debt_amount or 0) - abs(debt_account.balance)  # Lo que se ha pagado
        }
        
        return render_template('debts/detail.html',
                             debt_account=debt_account,
                             debt_info=debt_info,
                             transactions=transactions,
                             projection=projection)
    
    @staticmethod
    @login_required
    def make_debt_payment():
        """Realizar pago a una deuda"""
        if request.method == 'POST':
            try:
                debt_id = int(request.form.get('debt_id'))
                amount = float(request.form.get('amount'))
                payment_source = request.form.get('payment_source')  # account_id o 'cash'
                notes = request.form.get('notes')
                
                # Validaciones
                debt_account = Account.query.filter_by(
                    id=debt_id,
                    user_id=current_user.id,
                    is_debt_account=True
                ).first()
                
                if not debt_account:
                    flash('Cuenta de deuda no encontrada.', 'error')
                    return redirect(url_for('main.debt_accounts'))
                
                if amount <= 0:
                    flash('El monto del pago debe ser mayor a 0.', 'error')
                    return redirect(url_for('main.debt_detail', debt_id=debt_id))
                
                # Verificar que no se pague más de lo debido
                current_debt = abs(debt_account.balance)  # Para deudas, el balance representa lo que se debe
                if amount > current_debt:
                    flash('No puedes pagar más de lo que debes.', 'error')
                    return redirect(url_for('main.debt_detail', debt_id=debt_id))
                
                # Crear transacción de pago (reduce la deuda)
                payment_transaction = Transaction(
                    user_id=current_user.id,
                    account_id=debt_id,
                    amount=amount,
                    description=f'Pago a {debt_account.creditor_name}',
                    category='debt_payment',
                    transaction_type='expense',  # Para deudas, los pagos reducen el balance (son gastos del balance de deuda)
                    date=datetime.utcnow(),
                    notes=notes,
                    creditor_name=debt_account.creditor_name,
                    is_debt_payment=True
                )
                
                db.session.add(payment_transaction)
                
                # Si el pago es desde otra cuenta, crear transacción de gasto
                if payment_source and payment_source != 'cash':
                    source_account = Account.query.filter_by(
                        id=int(payment_source),
                        user_id=current_user.id
                    ).first()
                    
                    if source_account:
                        expense_transaction = Transaction(
                            user_id=current_user.id,
                            account_id=int(payment_source),
                            amount=amount,
                            description=f'Pago de deuda - {debt_account.creditor_name}',
                            category='debt_payment',
                            transaction_type='expense',
                            date=datetime.utcnow(),
                            notes=f'Transferencia a {debt_account.name}'
                        )
                        
                        db.session.add(expense_transaction)
                        source_account.update_balance()
                
                # Actualizar balance de la deuda
                debt_account.update_balance()
                
                db.session.commit()
                flash('Pago registrado exitosamente.', 'success')
                return redirect(url_for('main.debt_detail', debt_id=debt_id))
                
            except ValueError:
                flash('El monto debe ser un número válido.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Error al registrar el pago.', 'error')
        
        # Obtener cuentas para el formulario
        debt_id = request.args.get('debt_id')
        debt_account = None
        if debt_id:
            debt_account = Account.query.filter_by(
                id=debt_id,
                user_id=current_user.id,
                is_debt_account=True
            ).first()
        
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_debt_account=False,
            is_active=True
        ).all()
        
        return render_template('debts/make_payment.html',
                             debt_account=debt_account,
                             accounts=accounts)
    
    @staticmethod
    @login_required
    def apply_interests():
        """Aplicar intereses mensuales a todas las cuentas de deuda"""
        debt_accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_debt_account=True,
            is_active=True
        ).all()
        
        applied_count = 0
        total_interest = 0
        
        try:
            for debt_account in debt_accounts:
                interest_transaction = debt_account.apply_monthly_interest()
                if interest_transaction:
                    applied_count += 1
                    total_interest += interest_transaction.amount
            
            db.session.commit()
            
            if applied_count > 0:
                flash(f'Se aplicaron intereses a {applied_count} cuenta(s) de deuda. Total: ${total_interest:.2f}', 'success')
            else:
                flash('No se aplicaron intereses (sin deudas pendientes o tasas de 0%).', 'info')
                
        except Exception as e:
            db.session.rollback()
            flash('Error al aplicar intereses.', 'error')
        
        return redirect(url_for('main.debt_accounts'))
    
    @staticmethod
    @login_required
    def edit_debt_account(debt_id):
        """Editar cuenta de deuda"""
        debt_account = Account.query.filter_by(
            id=debt_id,
            user_id=current_user.id,
            is_debt_account=True
        ).first_or_404()
        
        if request.method == 'POST':
            try:
                # Campos básicos
                debt_account.name = request.form.get('name')
                debt_account.creditor_name = request.form.get('creditor_name')
                
                # Campos financieros
                original_amount = request.form.get('original_amount')
                if original_amount:
                    debt_account.original_debt_amount = float(original_amount)
                
                current_balance = request.form.get('current_balance')
                if current_balance:
                    # Para deudas, almacenar como valor positivo
                    debt_account.balance = float(current_balance)
                
                debt_account.interest_rate = float(request.form.get('interest_rate', 0))
                debt_account.minimum_payment = float(request.form.get('minimum_payment', 0))
                debt_account.payment_due_day = int(request.form.get('payment_due_day', 1))
                
                # Campos adicionales
                status = request.form.get('status')
                if status:
                    debt_account.status = status
                
                notes = request.form.get('notes')
                debt_account.notes = notes if notes else None
                
                db.session.commit()
                flash('Cuenta de deuda actualizada exitosamente.', 'success')
                return redirect(url_for('main.debt_detail', debt_id=debt_id))
                
            except ValueError:
                db.session.rollback()
                flash('Error en los datos ingresados. Verifica que los montos sean números válidos.', 'error')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al actualizar la cuenta de deuda: {str(e)}', 'error')

        # Render edit form (GET or after validation errors)
        return render_template('debts/edit.html', debt_account=debt_account)
