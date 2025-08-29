# backend/Dockerfile

FROM python:3.11-slim

# 1) Базовые системные зависимости (чтобы быстрее и стабильнее ставились колёса)
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# 2) Рабочая директория
WORKDIR /app

# 3) Ускоряем Python-логи и отключаем .pyc
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# 4) Ставим зависимости отдельно, чтобы кеш лучше работал
#    Предполагается, что requirements.txt лежит в папке backend/
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# 5) Копируем исходники приложения
COPY . /app

# 6) На всякий случай явно укажем PYTHONPATH
ENV PYTHONPATH=/app

# 7) (Не обязательно) EXPOSE для удобства локальной отладки
EXPOSE 8000

# 8) Команда запуска:
#    - "app.main:app" — путь до приложения FastAPI (файл backend/app/main.py => модуль app.main)
#    - --proxy-headers и --forwarded-allow-ips="*" — корректная работа за nginx-proxy
#    - --workers 2 — легкая параллельность (можно увеличить при необходимости)
CMD uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips="*" \
    --workers 2

