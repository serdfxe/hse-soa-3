import logging

import grpc
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.circuit_breaker import CircuitBreakerOpenError
from app.routers import flights, bookings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Booking Service API",
    description="""
## Сервис бронирования авиабилетов

### Типичный сценарий тестирования:
1. **GET /flights** — найти рейсы (`origin=SVO`, `destination=LED`)
2. **GET /flights/{id}** — посмотреть конкретный рейс
3. **POST /bookings** — забронировать (взять `flight_id` из шага 1)
4. **GET /bookings/{id}** — проверить бронирование
5. **POST /bookings/{id}/cancel** — отменить бронирование

### Готовые тестовые рейсы (созданы автоматически):
| ID | Рейс | Маршрут | Дата | Цена |
|----|------|---------|------|------|
| 1 | SU1234 | SVO→LED | 2026-04-01 | 3500 ₽ |
| 2 | SU5678 | SVO→AER | 2026-04-02 | 5200 ₽ |
| 3 | DP100  | LED→SVO | 2026-04-01 | 1990 ₽ |
| 4 | S7200  | DME→SVX | 2026-04-03 | 4100 ₽ |
| 5 | U6310  | SVX→LED | 2026-04-05 | 4800 ₽ |
| 6 | SU999  | SVO→LED | 2026-04-10 | 3200 ₽ (2 места — для теста нехватки мест) |

> Управление рейсами (создание/удаление): **http://localhost:8001/docs**
    """,
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
