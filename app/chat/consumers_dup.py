import json
import uuid
import asyncio
import structlog
from datetime import datetime
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from prometheus_client import Counter, Gauge
from asgiref.sync import sync_to_async
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

        self.message_count = await sync_to_async(self.get_message_count)(self.session_id)
        connection_gauge.inc()
        await self.accept()
        logger.info("WebSocket connected", session_id=self.session_id, request_id=str(uuid.uuid4()))

    def get_message_count(self, session_id):
        return session_store.get(session_id, 0)

    async def disconnect(self, close_code):
        connection_gauge.dec()

        # Save session before attempting to send goodbye message
        await sync_to_async(self.save_session)()

        # Try to send goodbye message, but handle potential connection issues
        try:
            await self.send(text_data=json.dumps({"bye": True, "total": self.message_count}))
        except Exception as e:
            logger.warning("Could not send goodbye message", error=str(e), session_id=self.session_id)

        logger.info("WebSocket disconnected", session_id=self.session_id, close_code=close_code,
                    request_id=str(uuid.uuid4()))

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

    def save_session(self):
        session_store[self.session_id] = self.message_count


# Heartbeat task
async def heartbeat():
    while getattr(settings, 'READY', False):
        await asyncio.sleep(30)  # Changed from 100 to 30 seconds for more reasonable heartbeat
        timestamp = datetime.utcnow().isoformat()

        if channel_layer:
            try:
                await channel_layer.group_send(
                    'chat', {'type': 'heartbeat.message', 'message': {'ts': timestamp}}
                )
                logger.info("Heartbeat sent", timestamp=timestamp, request_id=str(uuid.uuid4()))
            except Exception as e:
                logger.error("Failed to send heartbeat", error=str(e), request_id=str(uuid.uuid4()))
        else:
            logger.warning("Channel layer not available for heartbeat")

    logger.info("Heartbeat task stopped")