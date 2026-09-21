"""
WSGI & ASGI Entrypoint for Cloud Hosting (Render, Heroku, Railway, Gunicorn)
Provides native FastAPI ASGI callable for Uvicorn and Gunicorn UvicornWorker.
"""
import os
import sys

# Prevent Windows Controlled Folder Access (CFA) __pycache__ FileNotFoundError
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# Ensure backend directory is in sys.path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from api import app

# Expose both app and application for ASGI servers and UvicornWorker
app = app
application = app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", app_dir=backend_path, host="0.0.0.0", port=port)
