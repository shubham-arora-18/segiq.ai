import pytest
import json
import asyncio
import websockets
import os
import uuid
from websockets.exceptions import ConnectionClosed

# Get port from environment variable, default to 80
PORT = os.getenv('PORT', '80')
ENV = os.getenv('TARGET_ENV', '')
URI = f"ws://localhost:{PORT}/{ENV}/ws/chat/"


@pytest.mark.asyncio
async def test_websocket_counter():
    """Test WebSocket message counting functionality"""
    uri = f"{URI}?session_id={str(uuid.uuid4())}"

    async with websockets.connect(uri) as ws:
        # Send a test message
        await ws.send("test message 1")

        # Receive the count response
        response = json.loads(await ws.recv())
        assert response["count"] == 1

        # Send another message
        await ws.send("test message 2")

        # Receive the count response
        response = json.loads(await ws.recv())
        assert response["count"] == 2

        # Close the connection manually to test goodbye message
        await ws.close()


# Tests redis as well
@pytest.mark.asyncio
async def test_websocket_session_persistence():
    """Test that session data persists across connections"""
    uri = f"{URI}?session_id={str(uuid.uuid4())}"

    # First connection
    async with websockets.connect(uri) as ws1:
        await ws1.send("first message")
        response = json.loads(await ws1.recv())
        assert response["count"] == 1

        await ws1.send("second message")
        response = json.loads(await ws1.recv())
        assert response["count"] == 2

    # Second connection with same session_id should continue count
    async with websockets.connect(uri) as ws2:
        await ws2.send("third message")
        response = json.loads(await ws2.recv())
        assert response["count"] == 3  # Should continue from previous session


@pytest.mark.asyncio
async def test_websocket_basic_connection():
    """Smoke test - basic connection and message exchange"""
    uri = f"{URI}"

    try:
        async with websockets.connect(uri) as ws:
            # Test basic message send/receive
            await ws.send("hello")
            response = await ws.recv()

            # Should receive JSON response
            data = json.loads(response)
            assert "count" in data
            assert data["count"] == 1

    except Exception as e:
        pytest.fail(f"Basic WebSocket connection failed: {e}")


@pytest.mark.asyncio
async def test_websocket_multiple_messages():
    """Test multiple messages in sequence"""
    uri = f"{URI}?session_id={str(uuid.uuid4())}"

    async with websockets.connect(uri) as ws:
        for i in range(1, 6):  # Send 5 messages
            await ws.send(f"message {i}")
            response = json.loads(await ws.recv())
            assert response["count"] == i
