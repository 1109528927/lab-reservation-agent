FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .env.example .env.example
COPY sql ./sql
COPY scripts ./scripts
COPY src ./src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
