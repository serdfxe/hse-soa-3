import asyncio
import logging
import time
from enum import Enum

import grpc

from app.config import settings

logger = logging.getLogger(__name__)


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is in OPEN state."""
    pass


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker(grpc.aio.UnaryUnaryClientInterceptor):
    def __init__(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.failure_threshold = settings.cb_failure_threshold
        self.timeout = settings.cb_timeout
        self._lock = asyncio.Lock()

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        async with self._lock:
            if self.state == CircuitState.OPEN:
                elapsed = time.monotonic() - self.last_failure_time
                if elapsed >= self.timeout:
                    logger.info("Circuit breaker: OPEN -> HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError("Flight service is temporarily unavailable (circuit breaker open)")

        try:
            response = await continuation(client_call_details, request)
            await self._on_success()
            return response
        except grpc.RpcError as e:
            await self._on_failure(e)
            raise

    async def _on_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info("Circuit breaker: HALF_OPEN -> CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def _on_failure(self, error):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.state == CircuitState.HALF_OPEN:
                logger.info("Circuit breaker: HALF_OPEN -> OPEN")
                self.state = CircuitState.OPEN
            elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                logger.info(
                    f"Circuit breaker: CLOSED -> OPEN (failures: {self.failure_count})"
                )
                self.state = CircuitState.OPEN
