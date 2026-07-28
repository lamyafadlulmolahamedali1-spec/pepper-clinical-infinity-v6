"""Gunicorn production config — Pepper Clinical V6"""
import multiprocessing
bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
