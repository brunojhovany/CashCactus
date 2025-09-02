from app import create_app
from app.migrations_runner import init_auto_migration

app = create_app()

# Ejecutar migraciones automáticas si AUTO_MIGRATE=1
init_auto_migration(app)

if __name__ == '__main__':
    app.run()