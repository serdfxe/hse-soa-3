import logging
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import func, select

from app import flight_pb2, flight_pb2_grpc
from app.cache import cache
from app.config import settings
from app.database import AsyncSessionFactory
from app.models import Flight, FlightStatusEnum, ReservationStatusEnum, SeatReservation

logger = logging.getLogger(__name__)


def _flight_status_to_proto(status: FlightStatusEnum) -> int:
    mapping = {
        FlightStatusEnum.SCHEDULED: flight_pb2.SCHEDULED,
        FlightStatusEnum.DEPARTED: flight_pb2.DEPARTED,
        FlightStatusEnum.CANCELLED: flight_pb2.CANCELLED,
        FlightStatusEnum.COMPLETED: flight_pb2.COMPLETED,
    }
    return mapping.get(status, flight_pb2.SCHEDULED)


def _reservation_status_to_proto(status: ReservationStatusEnum) -> int:
    mapping = {
        ReservationStatusEnum.ACTIVE: flight_pb2.ACTIVE,
        ReservationStatusEnum.RELEASED: flight_pb2.RELEASED,
        ReservationStatusEnum.EXPIRED: flight_pb2.EXPIRED,
    }
    return mapping.get(status, flight_pb2.ACTIVE)


def _datetime_to_timestamp(dt: datetime) -> Timestamp:
    ts = Timestamp()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts.FromDatetime(dt)
    return ts


def _flight_to_proto(flight: Flight) -> flight_pb2.Flight:
    return flight_pb2.Flight(
        id=flight.id,
        flight_number=flight.flight_number,
        airline=flight.airline,
        origin=flight.origin,
        destination=flight.destination,
        departure_time=_datetime_to_timestamp(flight.departure_time),
        arrival_time=_datetime_to_timestamp(flight.arrival_time),
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        price=float(flight.price),
        status=_flight_status_to_proto(flight.status),
    )


def _flight_to_dict(flight: Flight) -> dict:
    return {
        "id": flight.id,
        "flight_number": flight.flight_number,
        "airline": flight.airline,
        "origin": flight.origin,
        "destination": flight.destination,
        "departure_time": flight.departure_time.isoformat() if flight.departure_time else None,
        "arrival_time": flight.arrival_time.isoformat() if flight.arrival_time else None,
        "total_seats": flight.total_seats,
        "available_seats": flight.available_seats,
        "price": float(flight.price),
        "status": flight.status.value if hasattr(flight.status, "value") else str(flight.status),
    }


def _check_auth(context) -> bool:
    """Check x-api-key from gRPC metadata. Returns True if valid."""
    metadata = dict(context.invocation_metadata())
    provided_key = metadata.get("x-api-key", "")
    return provided_key == settings.api_key


class FlightServicer(flight_pb2_grpc.FlightServiceServicer):

    async def SearchFlights(self, request, context):
        if not _check_auth(context):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")
            return flight_pb2.SearchFlightsResponse()

        origin = request.origin
        destination = request.destination
        date = request.date

        # Try cache first
        cached = await cache.get_search(origin, destination, date)
        if cached is not None:
            flights_proto = []
            for f_dict in cached:
                dep_ts = Timestamp()
                dep_ts.FromJsonString(f_dict["departure_time"] + "Z" if not f_dict["departure_time"].endswith("Z") else f_dict["departure_time"])
                arr_ts = Timestamp()
                arr_ts.FromJsonString(f_dict["arrival_time"] + "Z" if not f_dict["arrival_time"].endswith("Z") else f_dict["arrival_time"])

                status_map = {
                    "SCHEDULED": flight_pb2.SCHEDULED,
                    "DEPARTED": flight_pb2.DEPARTED,
                    "CANCELLED": flight_pb2.CANCELLED,
                    "COMPLETED": flight_pb2.COMPLETED,
                }
                flights_proto.append(flight_pb2.Flight(
                    id=f_dict["id"],
                    flight_number=f_dict["flight_number"],
                    airline=f_dict["airline"],
                    origin=f_dict["origin"],
                    destination=f_dict["destination"],
                    departure_time=dep_ts,
                    arrival_time=arr_ts,
                    total_seats=f_dict["total_seats"],
                    available_seats=f_dict["available_seats"],
                    price=f_dict["price"],
                    status=status_map.get(f_dict["status"], flight_pb2.SCHEDULED),
                ))
            return flight_pb2.SearchFlightsResponse(flights=flights_proto)

        # Query database
        async with AsyncSessionFactory() as session:
            query = select(Flight).where(Flight.status == FlightStatusEnum.SCHEDULED)
            if origin:
                query = query.where(Flight.origin == origin)
            if destination:
                query = query.where(Flight.destination == destination)
            if date:
                # Filter by date: DATE(departure_time) = date
                query = query.where(
                    func.date(Flight.departure_time) == date
                )
            result = await session.execute(query)
            flights = result.scalars().all()

        flights_data = [_flight_to_dict(f) for f in flights]
        await cache.set_search(origin, destination, date, flights_data)

        return flight_pb2.SearchFlightsResponse(
            flights=[_flight_to_proto(f) for f in flights]
        )

    async def GetFlight(self, request, context):
        if not _check_auth(context):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")
            return flight_pb2.GetFlightResponse()

        flight_id = request.flight_id

        # Try cache
        cached = await cache.get_flight(flight_id)
        if cached is not None:
            dep_ts = Timestamp()
            dep_str = cached["departure_time"]
            if not dep_str.endswith("Z") and "+" not in dep_str:
                dep_str += "Z"
            dep_ts.FromJsonString(dep_str)

            arr_ts = Timestamp()
            arr_str = cached["arrival_time"]
            if not arr_str.endswith("Z") and "+" not in arr_str:
                arr_str += "Z"
            arr_ts.FromJsonString(arr_str)

            status_map = {
                "SCHEDULED": flight_pb2.SCHEDULED,
                "DEPARTED": flight_pb2.DEPARTED,
                "CANCELLED": flight_pb2.CANCELLED,
                "COMPLETED": flight_pb2.COMPLETED,
            }
            flight_proto = flight_pb2.Flight(
                id=cached["id"],
                flight_number=cached["flight_number"],
                airline=cached["airline"],
                origin=cached["origin"],
                destination=cached["destination"],
                departure_time=dep_ts,
                arrival_time=arr_ts,
                total_seats=cached["total_seats"],
                available_seats=cached["available_seats"],
                price=cached["price"],
                status=status_map.get(cached["status"], flight_pb2.SCHEDULED),
            )
            return flight_pb2.GetFlightResponse(flight=flight_proto)

        # Query DB
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(Flight).where(Flight.id == flight_id)
            )
            flight = result.scalar_one_or_none()

        if flight is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
            return flight_pb2.GetFlightResponse()

        await cache.set_flight(flight_id, _flight_to_dict(flight))
        return flight_pb2.GetFlightResponse(flight=_flight_to_proto(flight))

    async def ReserveSeats(self, request, context):
        if not _check_auth(context):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")
            return flight_pb2.ReserveSeatsResponse()

        flight_id = request.flight_id
        seat_count = request.seat_count
        booking_id = request.booking_id

        async with AsyncSessionFactory() as session:
            async with session.begin():
                # Check idempotency: if reservation with booking_id already exists
                existing = await session.execute(
                    select(SeatReservation).where(SeatReservation.booking_id == booking_id)
                )
                existing_reservation = existing.scalar_one_or_none()
                if existing_reservation is not None:
                    return flight_pb2.ReserveSeatsResponse(
                        reservation_id=str(existing_reservation.id),
                        status=_reservation_status_to_proto(existing_reservation.status),
                    )

                # SELECT FOR UPDATE on flight to prevent race conditions
                flight_result = await session.execute(
                    select(Flight).where(Flight.id == flight_id).with_for_update()
                )
                flight = flight_result.scalar_one_or_none()

                if flight is None:
                    await context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
                    return flight_pb2.ReserveSeatsResponse()

                if flight.available_seats < seat_count:
                    await context.abort(
                        grpc.StatusCode.RESOURCE_EXHAUSTED,
                        f"Not enough seats: requested {seat_count}, available {flight.available_seats}"
                    )
                    return flight_pb2.ReserveSeatsResponse()

                # Decrement available seats
                flight.available_seats -= seat_count

                # Create reservation
                reservation = SeatReservation(
                    flight_id=flight_id,
                    booking_id=booking_id,
                    seat_count=seat_count,
                    status=ReservationStatusEnum.ACTIVE,
                )
                session.add(reservation)
                await session.flush()

                reservation_id = str(reservation.id)

        # Invalidate cache
        await cache.delete_flight(flight_id)
        await cache.delete_search("", "", "")  # Broad invalidation - also invalidate specific keys
        # More targeted invalidation would need origin/destination - invalidate by flight id
        # The search cache is harder to invalidate without storing reverse lookups
        # We do a best-effort invalidation for common patterns
        async with AsyncSessionFactory() as session:
            result = await session.execute(select(Flight).where(Flight.id == flight_id))
            updated_flight = result.scalar_one_or_none()
            if updated_flight:
                await cache.delete_search(updated_flight.origin, updated_flight.destination, "")

        return flight_pb2.ReserveSeatsResponse(
            reservation_id=reservation_id,
            status=flight_pb2.ACTIVE,
        )

    async def ReleaseReservation(self, request, context):
        if not _check_auth(context):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")
            return flight_pb2.ReleaseReservationResponse()

        booking_id = request.booking_id

        async with AsyncSessionFactory() as session:
            async with session.begin():
                # Find active reservation by booking_id
                res_result = await session.execute(
                    select(SeatReservation)
                    .where(
                        SeatReservation.booking_id == booking_id,
                        SeatReservation.status == ReservationStatusEnum.ACTIVE,
                    )
                    .with_for_update()
                )
                reservation = res_result.scalar_one_or_none()

                if reservation is None:
                    await context.abort(grpc.StatusCode.NOT_FOUND, "Active reservation not found")
                    return flight_pb2.ReleaseReservationResponse()

                # Get flight with FOR UPDATE
                flight_result = await session.execute(
                    select(Flight).where(Flight.id == reservation.flight_id).with_for_update()
                )
                flight = flight_result.scalar_one_or_none()

                if flight is None:
                    await context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
                    return flight_pb2.ReleaseReservationResponse()

                # Return seats
                flight.available_seats += reservation.seat_count

                # Mark reservation as released
                reservation.status = ReservationStatusEnum.RELEASED

                flight_id = flight.id
                origin = flight.origin
                destination = flight.destination

        # Invalidate cache
        await cache.delete_flight(flight_id)
        await cache.delete_search(origin, destination, "")

        return flight_pb2.ReleaseReservationResponse(success=True)
