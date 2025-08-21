FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies for matplotlib (Agg) and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
	libfreetype6 libpng16-16 fonts-dejavu-core \
	&& rm -rf /var/lib/apt/lists/*

RUN apt-get install -y build-essential python3-dev

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure instance folder exists for SQLite default path
RUN mkdir -p /app/instance

EXPOSE 8000

ENV FLASK_APP=run.py \
	FLASK_ENV=production

# Start with Gunicorn in production
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "run:app"]