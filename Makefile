# Makefile para el proyecto de finanzas personales

.PHONY: help install test test-unit test-integration test-coverage clean run dev

# Variables
PYTHON = python3
PIP = pip3
FLASK_APP = run.py

help:  ## Mostrar esta ayuda
	@echo "Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Instalar dependencias
	$(PIP) install -r requirements.txt

test:  ## Ejecutar todos los tests
	$(PYTHON) -m pytest tests/ -v

test-unit:  ## Ejecutar solo tests unitarios
	$(PYTHON) -m pytest tests/test_models.py tests/test_services.py tests/test_report_service.py -v

test-integration:  ## Ejecutar solo tests de integración
	$(PYTHON) -m pytest tests/test_integration.py tests/test_controllers.py -v

test-coverage:  ## Ejecutar tests con reporte de cobertura
	$(PYTHON) -m pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

test-models:  ## Ejecutar tests de modelos
	$(PYTHON) -m pytest tests/test_models.py -v

test-controllers:  ## Ejecutar tests de controladores
	$(PYTHON) -m pytest tests/test_controllers.py -v

test-services:  ## Ejecutar tests de servicios
	$(PYTHON) -m pytest tests/test_services.py tests/test_report_service.py -v

test-watch:  ## Ejecutar tests en modo watch (requiere pytest-watch)
	$(PYTHON) -m ptw tests/

clean:  ## Limpiar archivos temporales
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage

run:  ## Ejecutar la aplicación
	FLASK_APP=$(FLASK_APP) $(PYTHON) -m flask run

dev:  ## Ejecutar la aplicación en modo desarrollo
	FLASK_APP=$(FLASK_APP) FLASK_ENV=development $(PYTHON) -m flask run --debug

init-db:  ## Inicializar base de datos
	FLASK_APP=$(FLASK_APP) $(PYTHON) -c "from app import db; db.create_all()"

lint:  ## Ejecutar linter
	$(PYTHON) -m flake8 app/ tests/

format:  ## Formatear código
	$(PYTHON) -m black app/ tests/

requirements:  ## Generar requirements.txt actualizado
	$(PIP) freeze > requirements.txt

docker-build:  ## Construir imagen Docker
	docker build -t finanzas-app .

docker-run:  ## Ejecutar en Docker
	docker run -p 5000:5000 finanzas-app

# Comandos para desarrollo
setup-dev:  ## Configurar entorno de desarrollo
	$(PIP) install -r requirements.txt
	$(MAKE) init-db

check:  ## Verificar que todo funciona correctamente
	$(MAKE) lint
	$(MAKE) test
	@echo "✅ Todas las verificaciones pasaron!"
