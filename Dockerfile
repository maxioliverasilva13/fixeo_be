FROM python:3.11-slim

# Single-stage: avoids copying a large /prefix between stages (peaks Railway builder disk less).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app/

RUN mkdir -p /app/media /app/staticfiles \
    && chmod +x railway_start.sh

EXPOSE 8000

# Railway overrides this via service "Start Command"; use railway_start.sh for prod.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
