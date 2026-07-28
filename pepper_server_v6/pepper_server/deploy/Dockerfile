FROM python:3.12-slim

# Security: non-root user
RUN groupadd -r pepper && useradd -r -g pepper pepper

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN mkdir -p data logs && chown -R pepper:pepper /app

USER pepper
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["gunicorn", "app.main:app", "-c", "gunicorn_conf.py"]
