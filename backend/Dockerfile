FROM python:3.13-slim
WORKDIR /srv
COPY backend/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /srv/backend
COPY alembic.ini /srv/alembic.ini
ENV PYTHONPATH=/srv/backend PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home support && mkdir -p /srv/data/uploads && chown -R support /srv/data
USER support
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--forwarded-allow-ips", "*"]
