FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 cloud
COPY --chown=cloud:cloud app ./app
COPY --chown=cloud:cloud migrations ./migrations
COPY --chown=cloud:cloud alembic.ini .
COPY --chown=cloud:cloud scripts/create_admin.py ./scripts/create_admin.py
USER cloud
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
