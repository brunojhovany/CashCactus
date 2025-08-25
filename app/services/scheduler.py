from apscheduler.schedulers.background import BackgroundScheduler
from app.services.payment_reminder_service import PaymentReminderService
from app.services.daily_maintenance_service import DailyMaintenanceService
import atexit
from zoneinfo import ZoneInfo  # Python 3.11 stdlib

# Nota: El scheduler se inicializa con la zona horaria configurada en app.config['TIMEZONE'].
# Si no se establece, por defecto es UTC (ver Config.TIMEZONE). Esto evita que tareas "9:00"
# se ejecuten a la hora equivocada cuando el servidor corre en UTC pero se espera hora local.

scheduler = None

def init_scheduler(app):
    """Inicializar el scheduler para tareas programadas"""
    global scheduler
    
    if scheduler is None:
        # Obtener timezone desde configuración (fallback a UTC si inválida)
        tz_name = getattr(app.config, 'TIMEZONE', None) or app.config.get('TIMEZONE', 'UTC')
        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = ZoneInfo('UTC')
            app.logger.warning('TIMEZONE "%s" inválida, usando UTC', tz_name)

        scheduler = BackgroundScheduler(timezone=tzinfo)

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

    # Programar actualización de recordatorios diariamente a las 09:00 (zona configurada)
        scheduler.add_job(
            func=with_app_context(PaymentReminderService.update_all_credit_card_reminders),
            trigger="cron",
            hour=9,
            minute=0,
            id='update_reminders'
        )

    # Mantenimiento diario: ajustar cuentas y actualizar balances a las 03:00 (zona configurada)
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
