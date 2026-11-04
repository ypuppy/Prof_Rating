# The API server: FastAPI on uvicorn. Built and run by deploy/docker-compose.yml
FROM python:3.14-slim

# Print logs straight away, and don't write .pyc files into the image
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Dependencies first: this layer is reused until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Don't run as root inside the container
RUN useradd --create-home app
USER app

EXPOSE 8000
# Bring the database schema up to date, then serve. --proxy-headers: trust Caddy's
# X-Forwarded-* headers (only Caddy can reach this port, inside the Docker network)
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
