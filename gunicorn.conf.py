import os

# Gunicorn configuration optimized for Render Free tier (512MB RAM)
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 1
threads = 2
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
worker_class = "gthread"
preload_app = False
accesslog = "-"
errorlog = "-"
loglevel = "info"
