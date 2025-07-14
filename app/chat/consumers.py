import json
import uuid
import asyncio
import structlog
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

# In-memory session store
session_store = {}


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Parse query string properly
        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)
        self.session_id = query_params.get('session_id', [str(uuid.uuid4())])[0]

        self.message_count = await self.get_message_count(self.session_id)
        connection_gauge.inc()

        # Join the chat group for heartbeat messages
        await self.channel_layer.group_add('chat', self.channel_name)
        await self.accept()

        logger.info("WebSocket connected", session_id=self.session_id, request_id=str(uuid.uuid4()))

    async def get_message_count(self, session_id):
        return session_store.get(session_id, 0)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('chat', self.channel_name)
        await self.save_session()

        if settings.SIGTERM_SIGNAL_RECEIVED:
            close_code = 1001

        logger.info("WebSocket disconnected", session_id=self.session_id,
                    close_code=close_code, request_id=str(uuid.uuid4()))
        connection_gauge.dec()

    async def receive(self, text_data):
        try:
            self.message_count += 1
            message_counter.inc()
            await self.send(text_data=json.dumps({"count": self.message_count}))
            logger.info("Message received", session_id=self.session_id, count=self.message_count,
                        request_id=str(uuid.uuid4()))
        except Exception as e:
            error_counter.inc()
            logger.error("Error processing message", error=str(e), session_id=self.session_id,
                         request_id=str(uuid.uuid4()))

    async def heartbeat_message(self, event):
        """Handle heartbeat messages sent to the chat group"""
        try:
            await self.send(text_data=json.dumps({
                "type": "heartbeat",
                "message": event["message"]
            }))
        except Exception as e:
            logger.error("Failed to send heartbeat to client", error=str(e), session_id=self.session_id)

    async def save_session(self):
        """Async method for saving session - no thread pool overhead"""
        session_store[self.session_id] = self.message_count


# Heartbeat task
async def heartbeat():
    while getattr(settings, 'READY', False):
        await asyncio.sleep(2)
        timestamp = datetime.utcnow().isoformat()
        await channel_layer.group_send(
            'chat', {'type': 'heartbeat.message', 'message': {'ts': timestamp}}
        )
        logger.info("Heartbeat sent", timestamp=timestamp, request_id=None)

    logger.info("Heartbeat task stopped")
