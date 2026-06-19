"""
QyverixAI — Backend API
FastAPI application with advanced middleware, rate limiting, and full analysis engine.
"""

import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .observability import (
    initialise_app_info,
    prometheus_metrics_middleware,
)
from .routers import (
    analyze,
    auth,
    chat,
    debugging,
    explanation,
)
from .routers import health as health_router
from .routers import (
    history,
)
from .routers import metrics as metrics_router
from .routers import (
    share,
    subscribe,
    suggestions,
    upload_file,
    user_data,
)
