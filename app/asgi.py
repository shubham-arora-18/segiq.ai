import os
import uuid
import asyncio
from contextlib import asynccontextmanager

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from app.chat.routing import websocket_urlpatterns
from django.conf import settings
from app.chat.consumers import heartbeat
from starlette.applications import Starlette
from starlette.routing import Mount
import structlog

logger = structlog.get_logger(__name__)

# Create the Django ASGI application
django_application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(websocket_urlpatterns),
})


async def startup():
    settings.READY = True
    logger.info("Starting heartbeat task", request_id=str(uuid.uuid4()))
    asyncio.create_task(heartbeat())


async def shutdown():
    settings.READY = False
    await asyncio.sleep(1)  # Allow in-flight messages to complete
    logger.info("Server shutdown complete", request_id=str(uuid.uuid4()))


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
