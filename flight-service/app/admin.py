from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models import Flight, FlightStatusEnum, SeatReservation

app = FastAPI(
    title="Flight Service — Admin API",
    description="Управление рейсами (для тестирования). gRPC API недоступен через Swagger.",
    version="1.0.0",
)


class CreateFlightRequest(BaseModel):
    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    total_seats: int
    price: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "flight_number": "SU1234",
                "airline": "Аэрофлот",
                "origin": "SVO",
                "destination": "LED",
                "departure_time": "2026-04-01T10:00:00Z",
                "arrival_time": "2026-04-01T11:20:00Z",
                "total_seats": 150,
                "price": 3500.00,
            }
        }
    }


def flight_to_dict(f: Flight) -> dict:
    return {
        "id": f.id,
        "flight_number": f.flight_number,
        "airline": f.airline,
        "origin": f.origin,
        "destination": f.destination,
        "departure_time": f.departure_time.isoformat(),
        "arrival_time": f.arrival_time.isoformat(),
        "total_seats": f.total_seats,
        "available_seats": f.available_seats,
        "price": float(f.price),
        "status": f.status.value,
    }


@app.get("/admin/flights", summary="Список всех рейсов")
async def list_flights():
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Flight).order_by(Flight.departure_time))
        flights = result.scalars().all()
    return [flight_to_dict(f) for f in flights]


@app.get("/admin/flights/{flight_id}", summary="Получить рейс по ID")
async def get_flight(flight_id: int):
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Flight).where(Flight.id == flight_id))
        flight = result.scalar_one_or_none()
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight_to_dict(flight)


@app.post("/admin/flights", status_code=201, summary="Создать рейс")
async def create_flight(payload: CreateFlightRequest):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            flight = Flight(
                flight_number=payload.flight_number,
                airline=payload.airline,
                origin=payload.origin.upper(),
                destination=payload.destination.upper(),
                departure_time=payload.departure_time,
                arrival_time=payload.arrival_time,
                total_seats=payload.total_seats,
                available_seats=payload.total_seats,
                price=payload.price,
                status=FlightStatusEnum.SCHEDULED,
            )
            session.add(flight)
            await session.flush()
            return flight_to_dict(flight)


@app.delete("/admin/flights/{flight_id}", summary="Удалить рейс")
async def delete_flight(flight_id: int):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            result = await session.execute(select(Flight).where(Flight.id == flight_id))
            flight = result.scalar_one_or_none()
            if flight is None:
                raise HTTPException(status_code=404, detail="Flight not found")
            await session.delete(flight)
    return {"detail": "deleted"}


@app.get("/admin/reservations", summary="Список всех резерваций")
async def list_reservations():
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(SeatReservation).order_by(SeatReservation.created_at.desc()))
        reservations = result.scalars().all()
    return [
        {
            "id": r.id,
            "flight_id": r.flight_id,
            "booking_id": r.booking_id,
            "seat_count": r.seat_count,
            "status": r.status.value,
            "created_at": r.created_at.isoformat(),
        }
        for r in reservations
    ]


@app.get("/health")
async def health():
    return {"status": "ok"}
