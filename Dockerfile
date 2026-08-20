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

# Хостинг сам подставит порт через переменную окружения PORT —
# app.py уже это учитывает (os.environ.get("PORT", 8000)).
CMD ["python3", "app.py"]
