"""
cPanel/Passenger WSGI entrypoint.

cPanel's Python app runner expects a WSGI callable named ``application``.
The app itself is FastAPI/ASGI, so a2wsgi adapts it for Passenger.
"""
from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from a2wsgi import ASGIMiddleware

from app.main import app
from app.scheduler import start_scheduler

start_scheduler()

application = ASGIMiddleware(app)
