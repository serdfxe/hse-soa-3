import uuid
from datetime import datetime, timezone
import grpc
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app import grpc_client
from app.database import AsyncSessionFactory
from app.models import Booking, BookingStatusEnum

router = APIRouter()


class CreateBookingRequest(BaseModel):
    user_id: str
    flight_id: int
    passenger_name: str
    passenger_email: str
    seat_count: int


class BookingResponse(BaseModel):
    id: str
    user_id: str
    flight_id: int
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: float
    status: str
    created_at: str
    updated_at: str


def booking_to_dict(booking: Booking) -> dict:
    return {
        "id": str(booking.id),
        "user_id": booking.user_id,
        "flight_id": booking.flight_id,
        "passenger_name": booking.passenger_name,
        "passenger_email": booking.passenger_email,
        "seat_count": booking.seat_count,
        "total_price": float(booking.total_price),
        "status": booking.status.value if hasattr(booking.status, "value") else str(booking.status),
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
    }


@router.post("/bookings", status_code=201)
async def create_booking(payload: CreateBookingRequest):
    # 1. Get flight info from flight-service
    try:
        flight = await grpc_client.get_flight(payload.flight_id)
    except grpc.RpcError as e:
        code = e.code() if hasattr(e, "code") and callable(e.code) else None
        if code == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        detail = e.details() if hasattr(e, "details") and callable(e.details) else str(e)
        raise HTTPException(status_code=502, detail=detail)

    if flight.available_seats < payload.seat_count:
        raise HTTPException(
            status_code=409,
            detail=f"Not enough seats: requested {payload.seat_count}, available {flight.available_seats}",
        )

    # Generate booking ID upfront for idempotency
    booking_id = str(uuid.uuid4())
    total_price = float(flight.price) * payload.seat_count

    # 2. Reserve seats in flight-service
    try:
        reservation = await grpc_client.reserve_seats(
            flight_id=payload.flight_id,
            seat_count=payload.seat_count,
            booking_id=booking_id,
        )
    except grpc.RpcError as e:
        code = e.code() if hasattr(e, "code") and callable(e.code) else None
        detail = e.details() if hasattr(e, "details") and callable(e.details) else str(e)
        if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise HTTPException(status_code=409, detail=detail)
        raise HTTPException(status_code=502, detail=detail)

    # 3. Persist booking in booking-service DB
    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                now = datetime.now(timezone.utc)
                booking = Booking(
                    id=uuid.UUID(booking_id),
                    user_id=payload.user_id,
                    flight_id=payload.flight_id,
                    passenger_name=payload.passenger_name,
                    passenger_email=payload.passenger_email,
                    seat_count=payload.seat_count,
                    total_price=total_price,
                    status=BookingStatusEnum.CONFIRMED,
                    created_at=now,
                    updated_at=now,
                )
                session.add(booking)
    except Exception as e:
        # Compensate: release the reservation
        try:
            await grpc_client.release_reservation(booking_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to save booking: {str(e)}")

    return booking_to_dict(booking)


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str):
    try:
        booking_uuid = uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Booking).where(Booking.id == booking_uuid)
        )
        booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    return booking_to_dict(booking)


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str):
    try:
        booking_uuid = uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")

    async with AsyncSessionFactory() as session:
        async with session.begin():
            result = await session.execute(
                select(Booking).where(Booking.id == booking_uuid).with_for_update()
            )
            booking = result.scalar_one_or_none()

            if booking is None:
                raise HTTPException(status_code=404, detail="Booking not found")

            if booking.status == BookingStatusEnum.CANCELLED:
                raise HTTPException(status_code=409, detail="Booking is already cancelled")

            # Release seats in flight-service
            try:
                await grpc_client.release_reservation(booking_id)
            except grpc.RpcError as e:
                code = e.code() if hasattr(e, "code") and callable(e.code) else None
                # If NOT_FOUND, reservation may already be released - proceed with cancellation
                if code != grpc.StatusCode.NOT_FOUND:
                    detail = e.details() if hasattr(e, "details") and callable(e.details) else str(e)
                    raise HTTPException(status_code=502, detail=detail)

            booking.status = BookingStatusEnum.CANCELLED
            booking.updated_at = datetime.now(timezone.utc)

    return booking_to_dict(booking)


@router.get("/bookings")
async def list_bookings(user_id: str = Query(..., description="Filter bookings by user ID")):
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Booking).where(Booking.user_id == user_id).order_by(Booking.created_at.desc())
        )
        bookings = result.scalars().all()

    return [booking_to_dict(b) for b in bookings]
