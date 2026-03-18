# ER Diagram

```mermaid
erDiagram
    FLIGHTS {
        bigint id PK "autoincrement"
        varchar(10) flight_number "NOT NULL"
        varchar(100) airline "NOT NULL"
        varchar(3) origin "IATA code, NOT NULL"
        varchar(3) destination "IATA code, NOT NULL"
        timestamptz departure_time "NOT NULL"
        timestamptz arrival_time "NOT NULL"
        int total_seats "NOT NULL, CHECK > 0"
        int available_seats "NOT NULL, CHECK >= 0"
        numeric(10,2) price "NOT NULL, CHECK > 0"
        flightstatus status "SCHEDULED|DEPARTED|CANCELLED|COMPLETED"
    }

    SEAT_RESERVATIONS {
        bigint id PK "autoincrement"
        bigint flight_id FK "NOT NULL"
        varchar(36) booking_id "UNIQUE, NOT NULL"
        int seat_count "NOT NULL"
        reservationstatus status "ACTIVE|RELEASED|EXPIRED"
        timestamptz created_at "NOT NULL"
        timestamptz updated_at "NOT NULL"
    }

    BOOKINGS {
        uuid id PK "gen_random_uuid()"
        varchar user_id "NOT NULL"
        bigint flight_id "reference to Flight Service"
        varchar passenger_name "NOT NULL"
        varchar passenger_email "NOT NULL"
        int seat_count "NOT NULL"
        numeric(10,2) total_price "NOT NULL"
        bookingstatus status "CONFIRMED|CANCELLED"
        timestamptz created_at "NOT NULL"
        timestamptz updated_at "NOT NULL"
    }

    FLIGHTS ||--o{ SEAT_RESERVATIONS : "has reservations"
```

## Notes

- `FLIGHTS` and `SEAT_RESERVATIONS` reside in the **Flight Service** database (`flight_db`).
- `BOOKINGS` resides in the **Booking Service** database (`booking_db`).
- `BOOKINGS.flight_id` is a logical reference to `FLIGHTS.id` across service boundaries (no FK constraint).
- `BOOKINGS.id` is used as the `booking_id` in `SEAT_RESERVATIONS` to link a booking to its seat reservation for idempotency.
- Unique constraint on `FLIGHTS(flight_number, DATE(departure_time))` ensures no duplicate flights per day.
- Unique constraint on `SEAT_RESERVATIONS(booking_id)` ensures idempotent seat reservation.
