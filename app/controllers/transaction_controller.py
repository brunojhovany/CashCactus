from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.account import Account
from app.models.credit_card import CreditCard
from app.services.transaction_service import TransactionService, TransactionDTO
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TransactionController:
    
    @staticmethod
    @login_required
    def list_transactions():
        try:
            page = request.args.get("page", 1, type=int)
            account_id = request.args.get("account_id", type=int)
            category = request.args.get("category")
            transaction_type = request.args.get("transaction_type")
            
            result = TransactionService.get_user_transactions(
                user_id=current_user.id,
                page=page,
                per_page=20,
                account_id=account_id,
                category=category,
                transaction_type=transaction_type
            )
            
            accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
            categories = TransactionService.get_transaction_categories()
            
            return render_template(
                "transactions/list.html",
                transactions=result["pagination"],
                accounts=accounts,
                categories=categories
            )
            
        except Exception as e:
            logger.exception(f"Error al listar transacciones para user {current_user.id}")
            flash("Error al cargar transacciones", "error")
            return redirect(url_for("main.dashboard"))
    
    @staticmethod
    @login_required
    def list_account_transactions(account_id):
        try:
            account = Account.query.filter_by(
                id=account_id, 
                user_id=current_user.id
            ).first_or_404()
            
            page = request.args.get("page", 1, type=int)
            category = request.args.get("category")
            transaction_type = request.args.get("transaction_type")
            
            result = TransactionService.get_user_transactions(
                user_id=current_user.id,
                page=page,
                per_page=20,
                account_id=account_id,
                category=category,
                transaction_type=transaction_type
            )
            
            categories = TransactionService.get_transaction_categories()
            
            return render_template(
                "transactions/account_list.html",
                transactions=result["pagination"],
                account=account,
                categories=categories
            )
            
        except Exception as e:
            logger.exception(f"Error al listar transacciones de cuenta {account_id}")
            flash("Error al cargar transacciones de la cuenta", "error")
            return redirect(url_for("main.dashboard"))
    
    @staticmethod
    @login_required
    def create_transaction():
        if request.method == "POST":
            try:
                dto = TransactionDTO.from_form(request.form)
                transaction = TransactionService.create_transaction(
                    user_id=current_user.id,
                    dto=dto
                )
                
                flash("Transacción registrada exitosamente", "success")
                return redirect(url_for("main.transactions"))
                
            except ValueError as e:
                logger.warning(f"Validación fallida al crear transacción: {e}")
                flash(str(e), "error")
                
            except PermissionError as e:
                logger.warning(f"Usuario {current_user.id} sin permisos al crear transacción: {e}")
                flash(str(e), "error")
                return redirect(url_for("main.dashboard"))
                
            except Exception as e:
                logger.exception(f"Error inesperado al crear transacción")
                flash("Error al crear la transacción", "error")
        
        try:
            accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
            credit_cards = CreditCard.query.filter_by(user_id=current_user.id, is_active=True).all()
            preselected_account_id = request.args.get("account_id")
            categories = TransactionService.get_transaction_categories()
            
            return render_template(
                "transactions/create.html",
                accounts=accounts,
                credit_cards=credit_cards,
                categories=categories,
                current_date=datetime.now().strftime("%Y-%m-%d"),
                preselected_account_id=preselected_account_id
            )
            
        except Exception as e:
            logger.exception(f"Error al cargar formulario de creación de transacción")
            flash("Error al cargar formulario", "error")
            return redirect(url_for("main.dashboard"))
    
    @staticmethod
    @login_required
    def edit_transaction(transaction_id):
        transaction = TransactionService.get_transaction_by_id(transaction_id, current_user.id)
        if not transaction:
            flash("Transacción no encontrada", "error")
            return redirect(url_for("main.transactions"))
        
        if request.method == "POST":
            try:
                dto = TransactionDTO.from_form(request.form)
                TransactionService.update_transaction(
                    transaction_id=transaction_id,
                    user_id=current_user.id,
                    dto=dto
                )
                
                flash("Transacción actualizada exitosamente", "success")
                return redirect(url_for("main.transactions"))
                
            except ValueError as e:
                logger.warning(f"Validación fallida al actualizar transacción {transaction_id}: {e}")
                flash(str(e), "error")
                
            except PermissionError as e:
                logger.warning(f"Usuario {current_user.id} sin permisos al actualizar transacción {transaction_id}: {e}")
                flash(str(e), "error")
                return redirect(url_for("main.dashboard"))
                
            except Exception as e:
                logger.exception(f"Error inesperado al actualizar transacción {transaction_id}")
                flash("Error al actualizar la transacción", "error")
        
        try:
            accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
            credit_cards = CreditCard.query.filter_by(user_id=current_user.id, is_active=True).all()
            categories = TransactionService.get_transaction_categories()
            
            return render_template(
                "transactions/edit.html",
                transaction=transaction,
                accounts=accounts,
                credit_cards=credit_cards,
                categories=categories
            )
            
        except Exception as e:
            logger.exception(f"Error al cargar formulario de edición de transacción {transaction_id}")
            flash("Error al cargar formulario", "error")
            return redirect(url_for("main.transactions"))
    
    @staticmethod
    @login_required
    def delete_transaction(transaction_id):
        try:
            TransactionService.delete_transaction(
                transaction_id=transaction_id,
                user_id=current_user.id
            )
            
            flash("Transacción eliminada exitosamente. Balances actualizados automáticamente.", "success")
            
        except PermissionError:
            logger.warning(f"Usuario {current_user.id} sin permisos al eliminar transacción {transaction_id}")
            flash("Transacción no encontrada", "error")
            
        except Exception as e:
            logger.exception(f"Error al eliminar transacción {transaction_id}")
            flash("Error al eliminar la transacción", "error")
        
        return redirect(url_for("main.transactions"))
