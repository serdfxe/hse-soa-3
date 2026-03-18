import asyncio
import logging

import grpc

from app import flight_pb2, flight_pb2_grpc
from app.circuit_breaker import CircuitBreaker
from app.config import settings

logger = logging.getLogger(__name__)

# Retry only for these status codes
RETRYABLE_CODES = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}
MAX_RETRIES = 3

circuit_breaker = CircuitBreaker()


def _get_metadata():
    return [("x-api-key", settings.flight_service_api_key)]


async def _with_retry(func, *args, **kwargs):
    """Execute gRPC call with retry logic."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except grpc.RpcError as e:
            code = e.code() if hasattr(e, "code") and callable(e.code) else None
            if code in RETRYABLE_CODES:
                delay = 0.1 * (2 ** attempt)  # 100ms, 200ms, 400ms
                logger.warning(
                    f"Retryable error {code}, attempt {attempt + 1}/{MAX_RETRIES}, retry in {delay}s"
                )
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
            else:
                raise
    raise last_error


def _get_channel():
    return grpc.aio.insecure_channel(
        settings.flight_service_url,
        interceptors=[circuit_breaker],
    )


async def search_flights(origin: str, destination: str, date: str = "") -> list:
    async with _get_channel() as channel:
        stub = flight_pb2_grpc.FlightServiceStub(channel)
        req = flight_pb2.SearchFlightsRequest(
            origin=origin, destination=destination, date=date
        )
        resp = await _with_retry(stub.SearchFlights, req, metadata=_get_metadata())
        return list(resp.flights)


async def get_flight(flight_id: int):
    async with _get_channel() as channel:
        stub = flight_pb2_grpc.FlightServiceStub(channel)
        req = flight_pb2.GetFlightRequest(flight_id=flight_id)
        resp = await _with_retry(stub.GetFlight, req, metadata=_get_metadata())
        return resp.flight


async def reserve_seats(flight_id: int, seat_count: int, booking_id: str):
    async with _get_channel() as channel:
        stub = flight_pb2_grpc.FlightServiceStub(channel)
        req = flight_pb2.ReserveSeatsRequest(
            flight_id=flight_id, seat_count=seat_count, booking_id=booking_id
        )
        resp = await _with_retry(stub.ReserveSeats, req, metadata=_get_metadata())
        return resp


async def release_reservation(booking_id: str):
    async with _get_channel() as channel:
        stub = flight_pb2_grpc.FlightServiceStub(channel)
        req = flight_pb2.ReleaseReservationRequest(booking_id=booking_id)
        resp = await _with_retry(stub.ReleaseReservation, req, metadata=_get_metadata())
        return resp
