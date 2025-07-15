import json
import uuid
import asyncio
import structlog
import redis.asyncio as redis
from datetime import datetime
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from prometheus_client import Counter, Gauge
from channels.layers import get_channel_layer
from django.conf import settings

logger = structlog.get_logger(__name__)
channel_layer = get_channel_layer()

# Metrics
message_counter = Counter('websocket_messages_total', 'Total messages received')
connection_gauge = Gauge('websocket_active_connections', 'Active WebSocket connections')
error_counter = Counter('websocket_errors_total', 'Total WebSocket errors')

# Redis connection pool
redis_pool = None


async def get_redis():
    """Get Redis connection"""
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL)
    return redis.Redis(connection_pool=redis_pool)


class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.message_count = None
        self.session_id = None

    async def connect(self):
        # Parse query string properly
        request_id = str(uuid.uuid4())
        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)
        self.session_id = query_params.get('session_id', [str(uuid.uuid4())])[0]
        self.message_count = await self.get_message_count(self.session_id)
        connection_gauge.inc()

        # Join the chat group for heartbeat messages
        await self.channel_layer.group_add('chat', self.channel_name)
        await self.accept()

        logger.info("WebSocket connected", session_id=self.session_id, request_id=request_id)

    async def get_message_count(self, session_id):
        """Get message count from Redis"""
        try:
            r = await get_redis()
            count = await r.get(f"session:{session_id}:count")
            return int(count) if count else 0
        except Exception as e:
            logger.error("Failed to get session from Redis", error=str(e), session_id=session_id)
            return 0

    async def save_message_count(self):
        """Save message count to Redis with TTL"""
        try:
            r = await get_redis()
            await r.setex(f"session:{self.session_id}:count", 3600, self.message_count)  # 1 hour TTL
        except Exception as e:
            logger.error("Failed to save session to Redis", error=str(e), session_id=self.session_id)

    async def disconnect(self, close_code):
        request_id = str(uuid.uuid4())
        await self.channel_layer.group_discard('chat', self.channel_name)

        if settings.SIGTERM_SIGNAL_RECEIVED:
            close_code = 1001

        logger.info("WebSocket disconnected", session_id=self.session_id,
                    close_code=close_code, request_id=request_id)
        connection_gauge.dec()

    async def receive(self, text_data):
        request_id = str(uuid.uuid4())
        try:
            self.message_count += 1
            message_counter.inc()
            await self.save_message_count()  # Persist after each message
            await self.send(text_data=json.dumps({"count": self.message_count}))
            logger.info("Message received", session_id=self.session_id, count=self.message_count,
                        request_id=request_id)
        except Exception as e:
            error_counter.inc()
            logger.error("Error processing message", error=str(e), session_id=self.session_id,
                         request_id=request_id)

    async def heartbeat_message(self, event):
        """Handle heartbeat messages sent to the chat group"""
        try:
            await self.send(text_data=json.dumps({
                "type": "heartbeat",
                "message": event["message"]
            }))
        except Exception as e:
            logger.error("Failed to send heartbeat to client", error=str(e), session_id=self.session_id)


# Heartbeat task
async def heartbeat():
    while getattr(settings, 'READY', False):
        await asyncio.sleep(30)
        timestamp = datetime.utcnow().isoformat()
        await channel_layer.group_send(
            'chat', {'type': 'heartbeat.message', 'message': {'ts': timestamp}}
        )
        logger.info("Heartbeat sent", timestamp=timestamp)

    logger.info("Heartbeat task stopped")
