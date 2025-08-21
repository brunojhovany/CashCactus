from apscheduler.schedulers.background import BackgroundScheduler
from app.services.payment_reminder_service import PaymentReminderService
import atexit

scheduler = None

def init_scheduler(app):
    """Inicializar el scheduler para tareas programadas"""
    global scheduler
    
    if scheduler is None:
        scheduler = BackgroundScheduler()
        
        # Programar actualización de recordatorios diariamente a las 9:00 AM
        scheduler.add_job(
            func=PaymentReminderService.update_all_credit_card_reminders,
            trigger="cron",
            hour=9,
            minute=0,
            id='update_reminders'
        )
        
        scheduler.start()
        
        # Asegurar que el scheduler se cierre al terminar la aplicación
        atexit.register(lambda: scheduler.shutdown() if scheduler else None)
        
        app.logger.info('Scheduler iniciado exitosamente')

def get_scheduler():
    """Obtener la instancia del scheduler"""
    return scheduler
