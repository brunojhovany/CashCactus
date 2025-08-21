from apscheduler.schedulers.background import BackgroundScheduler
from app.services.payment_reminder_service import PaymentReminderService
from app.services.daily_maintenance_service import DailyMaintenanceService
import atexit

scheduler = None

def init_scheduler(app):
    """Inicializar el scheduler para tareas programadas"""
    global scheduler
    
    if scheduler is None:
        scheduler = BackgroundScheduler()

        # Helpers para ejecutar funciones con app_context
        def with_app_context(func):
            def _runner():
                try:
                    with app.app_context():
                        func()
                except Exception:
                    # Silenciar para evitar detener el scheduler; logs pueden añadirse si se requiere
                    pass
            return _runner

        # Programar actualización de recordatorios diariamente a las 9:00 AM
        scheduler.add_job(
            func=with_app_context(PaymentReminderService.update_all_credit_card_reminders),
            trigger="cron",
            hour=9,
            minute=0,
            id='update_reminders'
        )

        # Mantenimiento diario: ajustar cuentas y actualizar balances a las 03:00 AM
        scheduler.add_job(
            func=with_app_context(DailyMaintenanceService.run_daily_maintenance),
            trigger="cron",
            hour=3,
            minute=0,
            id='daily_maintenance'
        )
        
        scheduler.start()
        
        # Asegurar que el scheduler se cierre al terminar la aplicación
        atexit.register(lambda: scheduler.shutdown() if scheduler else None)
        
        app.logger.info('Scheduler iniciado exitosamente')

def get_scheduler():
    """Obtener la instancia del scheduler"""
    return scheduler
