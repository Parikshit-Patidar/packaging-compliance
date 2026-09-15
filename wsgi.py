"""
WSGI & ASGI Entrypoint for Cloud Hosting (Render, Heroku, Railway, Gunicorn)
Supports both ASGI (uvicorn.workers.UvicornWorker) and standard WSGI (via a2wsgi).
"""
import os
import sys

# Ensure backend directory is in sys.path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from api import app

# Expose 'app' for ASGI servers (e.g. uvicorn wsgi:app or gunicorn -k uvicorn.workers.UvicornWorker wsgi:app)
app = app

# Expose 'application' for WSGI servers (e.g. gunicorn wsgi:application or gunicorn wsgi)
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except Exception:
    application = app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", app_dir=backend_path, host="0.0.0.0", port=port)
