FROM python:3.11-slim

# Рабочая директория
WORKDIR /app

# Устанавливаем env для Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=1

# Копируем только зависимости, чтобы кешировалось
COPY backend/requirements.txt /app/requirements.txt

# Ставим зависимости (без кеша; binary-варианты для Postgres)
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt

# Копируем приложение
COPY backend /app/app

# Порт (для справки)
EXPOSE 8000

# Запуск Uvicorn
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*" --workers 2
