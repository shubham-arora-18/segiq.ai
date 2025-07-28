import json
import uuid
import time
import random
from locust import User, task, events
from websocket import create_connection, WebSocketTimeoutException
import os

PORT = os.getenv('PORT', '80')


class WebSocketUser(User):
    # Base Websocket User class
    weight = 0

    def __init__(self, environment):
        super().__init__(environment)
        self.ws = None
        self.session_id = str(uuid.uuid4())
        self.message_count = 0

    def on_start(self):
        """Called when a user starts"""
        self.connect_websocket()

    def on_stop(self):
        """Called when a user stops"""
        self.disconnect_websocket()

    def connect_websocket(self):
        """Establish WebSocket connection"""
        start_time = time.time()
        try:
            # WebSocket URL with session ID
            ws_url = f"ws://localhost:{PORT}/ws/chat/?session_id={self.session_id}"

            # Create WebSocket connection with timeout
            self.ws = create_connection(
                ws_url,
                timeout=40,
                enable_multithread=True
            )

            # Record successful connection
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="WebSocket",
                name="connect",
                response_time=total_time,
                response_length=0,
                exception=None,
                context={}
            )

        except Exception as e:
            # Record failed connection
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="WebSocket",
                name="connect",
                response_time=total_time,
                response_length=0,
                exception=e,
                context={}
            )
            self.ws = None

    def disconnect_websocket(self):
        """Close WebSocket connection"""
        if self.ws:
            try:
                start_time = time.time()
                self.ws.close()
                total_time = int((time.time() - start_time) * 1000)
                events.request.fire(
                    request_type="WebSocket",
                    name="disconnect",
                    response_time=total_time,
                    response_length=0,
                    exception=None,
                    context={}
                )
            except:
                pass
            self.ws = None

    def send_message(self, message):
        """Send message and measure response time"""
        if not self.ws:
            return

        start_time = time.time()
        try:
            # Send message
            self.ws.send(message)

            # Wait for response with timeout
            self.ws.settimeout(10)
            response = self.ws.recv()

            # Record successful message
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="WebSocket",
                name="send_message",
                response_time=total_time,
                response_length=len(response),
                exception=None,
                context={}
            )

            self.message_count += 1
            # Check for empty response before JSON parsing
            if not response or not response.strip():
                raise ValueError("Empty response received")

            return json.loads(response)

        except WebSocketTimeoutException:
            # Record timeout
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="WebSocket",
                name="send_message",
                response_time=total_time,
                response_length=0,
                exception=WebSocketTimeoutException("Response timeout"),
                context={}
            )
        except Exception as e:
            # Record other errors
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="WebSocket",
                name="send_message",
                response_time=total_time,
                response_length=0,
                exception=e,
                context={}
            )

    @task(2)
    def send_chat_message(self):
        """Send a chat message (most common action)"""
        message = f"Hello from user {self.session_id[:8]} - message {self.message_count + 1}"
        self.send_message(message)

    @task(1)
    def send_ping_message(self):
        """Send a ping message (less frequent)"""
        ping_message = {"type": "ping", "timestamp": time.time()}
        self.send_message(json.dumps(ping_message))

    def wait_time(self):
        """Wait time between messages (realistic user behavior)"""
        # Users don't send messages constantly
        # Wait 5-30 seconds between messages
        return random.uniform(5, 30)


# Configuration for different test scenarios
class ChatUser(WebSocketUser):
    """Regular chat user - sends messages frequently"""
    weight = 8  # 80% of users are regular chatters

    def wait_time(self):
        return random.uniform(2, 10)  # More active users


class LurkerUser(WebSocketUser):
    """Lurker user - connects but rarely sends messages"""
    weight = 2  # 20% of users are lurkers

    @task(1)
    def send_chat_message(self):
        """Lurkers send very few messages"""
        if random.random() < 0.1:  # Only 10% chance to send message
            super().send_chat_message()

    @task(0)  # Disable ping messages for lurkers
    def send_ping_message(self):
        pass

    def wait_time(self):
        return random.uniform(30, 120)  # Very inactive users
