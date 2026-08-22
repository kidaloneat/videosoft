# Гарантирует, что ffmpeg точно будет установлен, независимо от того,
# какой хостинг собирает образ (Render, Railway, Fly.io и т.п. — все
# умеют собирать обычный Dockerfile).

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Хостинг сам подставит порт через переменную окружения PORT.
# Gunicorn вместо встроенного dev-сервера Flask — надёжнее держит
# параллельные запросы (загрузка файлов + опрос прогресса одновременно)
# на слабом бесплатном тарифе Render. 1 worker — чтобы job-статусы в
# памяти (JOBS dict) были общими для всех запросов; 4 потока внутри —
# для параллельной обработки. Таймаут увеличен под медленную загрузку
# больших аудиофайлов с мобильного интернета.
CMD ["sh", "-c", "gunicorn --workers 1 --threads 4 --timeout 300 -b 0.0.0.0:${PORT:-8000} app:app"]
