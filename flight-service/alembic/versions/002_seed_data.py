"""Seed sample flights for testing

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000001

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO flights (flight_number, airline, origin, destination, departure_time, arrival_time, total_seats, available_seats, price, status)
        VALUES
            ('SU1234', 'Аэрофлот',       'SVO', 'LED', '2026-04-01 10:00:00+00', '2026-04-01 11:20:00+00', 150, 150, 3500.00, 'SCHEDULED'),
            ('SU5678', 'Аэрофлот',       'SVO', 'AER', '2026-04-02 08:30:00+00', '2026-04-02 11:00:00+00', 180, 180, 5200.00, 'SCHEDULED'),
            ('DP100',  'Победа',         'LED', 'SVO', '2026-04-01 14:00:00+00', '2026-04-01 15:20:00+00', 189, 189, 1990.00, 'SCHEDULED'),
            ('S7200',  'S7 Airlines',    'DME', 'SVX', '2026-04-03 06:15:00+00', '2026-04-03 08:30:00+00', 160, 160, 4100.00, 'SCHEDULED'),
            ('U6310',  'Уральские авиалинии', 'SVX', 'LED', '2026-04-05 12:00:00+00', '2026-04-05 14:45:00+00', 170, 170, 4800.00, 'SCHEDULED'),
            ('SU999',  'Аэрофлот',       'SVO', 'LED', '2026-04-10 18:00:00+00', '2026-04-10 19:20:00+00',   2,   2, 3200.00, 'SCHEDULED')
    """)


def downgrade() -> None:
    op.execute("DELETE FROM flights WHERE flight_number IN ('SU1234','SU5678','DP100','S7200','U6310','SU999')")
