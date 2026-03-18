import logging

import grpc
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.circuit_breaker import CircuitBreakerOpenError
from app.routers import flights, bookings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Booking Service",
    description="Flight booking service that communicates with Flight Service via gRPC",
    version="1.0.0",
)

# Include routers
app.include_router(flights.router, tags=["Flights"])
app.include_router(bookings.router, tags=["Bookings"])


@app.exception_handler(CircuitBreakerOpenError)
async def circuit_breaker_handler(request: Request, exc: CircuitBreakerOpenError):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
