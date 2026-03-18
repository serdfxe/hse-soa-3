from fastapi import APIRouter, HTTPException, Query

import grpc

from app import grpc_client

router = APIRouter()


def flight_to_dict(f):
    return {
        "id": f.id,
        "flight_number": f.flight_number,
        "airline": f.airline,
        "origin": f.origin,
        "destination": f.destination,
        "departure_time": f.departure_time.ToDatetime().isoformat(),
        "arrival_time": f.arrival_time.ToDatetime().isoformat(),
        "total_seats": f.total_seats,
        "available_seats": f.available_seats,
        "price": f.price,
        "status": f.status,
    }


@router.get("/flights")
async def search_flights(
    origin: str = Query(..., description="IATA origin airport code"),
    destination: str = Query(..., description="IATA destination airport code"),
    date: str = Query(default="", description="Filter date YYYY-MM-DD (optional)"),
):
    try:
        flights = await grpc_client.search_flights(origin, destination, date)
        return [flight_to_dict(f) for f in flights]
    except grpc.RpcError as e:
        detail = e.details() if hasattr(e, "details") and callable(e.details) else str(e)
        raise HTTPException(status_code=502, detail=detail)


@router.get("/flights/{flight_id}")
async def get_flight(flight_id: int):
    try:
        flight = await grpc_client.get_flight(flight_id)
        return flight_to_dict(flight)
    except grpc.RpcError as e:
        code = e.code() if hasattr(e, "code") and callable(e.code) else None
        if code == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        detail = e.details() if hasattr(e, "details") and callable(e.details) else str(e)
        raise HTTPException(status_code=502, detail=detail)
