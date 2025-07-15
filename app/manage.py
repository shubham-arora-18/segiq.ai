import os
import asyncio
import signal
import time
from contextlib import asynccontextmanager
import structlog
from prometheus_client import Gauge
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from starlette.applications import Starlette
from starlette.routing import Mount
from django.conf import settings

startup_start = time.time()
# Set Django settings module BEFORE importing chat modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
from app.chat.routing import websocket_urlpatterns
from app.chat.consumers import heartbeat

logger = structlog.get_logger(__name__)
startup_time = Gauge('sigiq_startup_time_seconds', 'Application startup time')
shutdown_time = Gauge('sigiq_shutdown_time_seconds', 'Application shutdown time')

# Create the Django ASGI application
django_application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(websocket_urlpatterns),
})


def signal_sigterm_handler(signum, frame):
    logger.info(f"Received signal {signum} (SIGTERM)")
    settings.SIGTERM_SIGNAL_RECEIVED = True


async def startup():
    settings.READY = True
    signal.signal(signal.SIGTERM, signal_sigterm_handler)
    logger.info("Starting heartbeat task")
    asyncio.create_task(heartbeat())
    startup_time.set(time.time() - startup_start)


async def shutdown():
    shutdown_start = time.time()
    settings.READY = False
    logger.info("Server shutdown complete")
    shutdown_time.set(time.time() - shutdown_start)


@asynccontextmanager
async def lifespan(app):
    # Startup
    await startup()
    yield
    # Shutdown
    await shutdown()


# Create Starlette app with lifespan management
application = Starlette(
    lifespan=lifespan,
    routes=[
        Mount("/", app=django_application),
    ]
)
