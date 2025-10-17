from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.services.account_service import AccountService, AccountDTO
import logging

logger = logging.getLogger(__name__)

class AccountController:
    """
    Controlador HTTP para cuentas bancarias.
    
    Responsabilidad: Solo coordinación de peticiones HTTP.
    Toda la lógica de negocio está delegada a AccountService.
    """
    
    @staticmethod
    @login_required
    def list_accounts():
        """Listar todas las cuentas del usuario"""
        try:
            accounts = AccountService.get_user_accounts(current_user.id, include_inactive=False)
            total_balance = AccountService.get_total_balance(current_user.id)
            
            return render_template('accounts/list.html', 
                                 accounts=accounts, 
                                 total_balance=total_balance)
        except Exception as e:
            logger.exception(f"Error al listar cuentas para user {current_user.id}")
            flash('Error al cargar las cuentas.', 'error')
            return render_template('accounts/list.html', accounts=[], total_balance=0)
    
    @staticmethod
    @login_required
    def create_account():
        """Crear nueva cuenta"""
        if request.method == 'POST':
            try:
                # Parsear y validar datos del formulario
                dto = AccountDTO.from_form(request.form)
                
                # Delegar creación al servicio
                account = AccountService.create_account(current_user.id, dto)
                
                flash('Cuenta creada exitosamente.', 'success')
                return redirect(url_for('main.accounts'))
                
            except ValueError as e:
                # Errores de validación
                flash(str(e), 'error')
                logger.warning(f"Validación fallida al crear cuenta para user {current_user.id}: {e}")
            except Exception as e:
                # Errores inesperados
                logger.exception(f'Error inesperado creando cuenta para user {current_user.id}')
                flash('Error al crear la cuenta.', 'error')
        
        # Obtener tipos de cuenta para el formulario
        account_types = AccountService.get_account_types()
        
        return render_template('accounts/create.html', account_types=account_types)
    
    @staticmethod
    @login_required
    def edit_account(account_id):
        """Editar cuenta existente"""
        # Obtener cuenta actual para mostrar en formulario
        account = AccountService.get_account_by_id(account_id, current_user.id)
        if not account:
            flash('Cuenta no encontrada.', 'error')
            return redirect(url_for('main.accounts'))
        
        if request.method == 'POST':
            try:
                # Parsear y validar datos del formulario
                dto = AccountDTO.from_form(request.form)
                
                # Delegar actualización al servicio
                account = AccountService.update_account(account_id, current_user.id, dto)
                
                flash('Cuenta actualizada exitosamente.', 'success')
                return redirect(url_for('main.accounts'))
                
            except ValueError as e:
                # Errores de validación
                flash(str(e), 'error')
                logger.warning(f"Validación fallida al actualizar cuenta {account_id}: {e}")
            except PermissionError as e:
                flash('No tienes permisos para editar esta cuenta.', 'error')
                return redirect(url_for('main.accounts'))
            except Exception as e:
                logger.exception(f'Error inesperado actualizando cuenta {account_id}')
                flash('Error al actualizar la cuenta.', 'error')
        
        # Obtener tipos de cuenta para el formulario
        account_types = AccountService.get_account_types()
        
        return render_template('accounts/edit.html', account=account, account_types=account_types)
    
    @staticmethod
    @login_required
    def delete_account(account_id):
        """Eliminar cuenta (desactivar)"""
        try:
            # Delegar desactivación al servicio
            AccountService.delete_account(account_id, current_user.id)
            flash('Cuenta eliminada exitosamente.', 'success')
        except PermissionError:
            flash('No tienes permisos para eliminar esta cuenta.', 'error')
        except Exception as e:
            logger.exception(f'Error eliminando cuenta {account_id}')
            flash('Error al eliminar la cuenta.', 'error')
        
        return redirect(url_for('main.accounts'))
    
    @staticmethod
    @login_required
    def account_details(account_id):
        """Ver detalles de una cuenta específica"""
        try:
            # Obtener estadísticas completas del servicio
            stats = AccountService.get_account_statistics(account_id, current_user.id)
            
            return render_template('accounts/details.html',
                                 account=stats['account'],
                                 recent_transactions=stats['recent_transactions'],
                                 monthly_income=stats['monthly_income'],
                                 monthly_expenses=stats['monthly_expenses'])
        except PermissionError:
            flash('No tienes permisos para ver esta cuenta.', 'error')
            return redirect(url_for('main.accounts'))
        except Exception as e:
            logger.exception(f'Error obteniendo detalles de cuenta {account_id}')
            flash('Error al cargar los detalles de la cuenta.', 'error')
            return redirect(url_for('main.accounts'))
    
    @staticmethod
    @login_required
    def get_account_balance(account_id):
        """API endpoint para obtener balance de cuenta"""
        try:
            account = AccountService.get_account_by_id(account_id, current_user.id)
            
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
        except Exception as e:
            logger.exception(f'Error obteniendo balance de cuenta {account_id}')
            return jsonify({
                'success': False,
                'message': 'Error al obtener balance'
            }), 500
