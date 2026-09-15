import os

# Port assigned by cloud hosting (Render, Heroku, Railway)
port = os.environ.get("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Use Uvicorn worker for high-speed async FastAPI handling
worker_class = "uvicorn.workers.UvicornWorker"
workers = 2
timeout = 120
keepalive = 5
loglevel = "info"
