"""
Compatibility module for cloud hosts defaulting to 'gunicorn your_application.wsgi'.
Directly connects to the Legal Metrology FastAPI engine.
"""
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(root_dir, "backend")

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from api import app

# Expose both app and application for ASGI servers and UvicornWorker
app = app
application = app
