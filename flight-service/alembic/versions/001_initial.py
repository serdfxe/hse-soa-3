"""Initial migration - flights and seat_reservations tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types (checkfirst=True — idempotent on re-runs)
    op.execute("CREATE TYPE IF NOT EXISTS flightstatus AS ENUM ('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED')")
    op.execute("CREATE TYPE IF NOT EXISTS reservationstatus AS ENUM ('ACTIVE', 'RELEASED', 'EXPIRED')")

    # create_type=False — enum already created above, don't try again
    op.create_table(
        'flights',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('flight_number', sa.String(10), nullable=False),
        sa.Column('airline', sa.String(100), nullable=False),
        sa.Column('origin', sa.String(3), nullable=False),
        sa.Column('destination', sa.String(3), nullable=False),
        sa.Column('departure_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('arrival_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_seats', sa.Integer(), nullable=False),
        sa.Column('available_seats', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column(
            'status',
            sa.Enum('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED',
                    name='flightstatus', create_type=False),
            nullable=False,
            server_default='SCHEDULED'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('available_seats >= 0', name='ck_flights_available_seats'),
        sa.CheckConstraint('total_seats > 0', name='ck_flights_total_seats'),
        sa.CheckConstraint('price > 0', name='ck_flights_price'),
    )

    # Unique index on (flight_number, DATE(departure_time))
    op.create_index(
        'uq_flight_number_date',
        'flights',
        ['flight_number', sa.text('DATE(departure_time)')],
        unique=True
    )

    op.create_table(
        'seat_reservations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('flight_id', sa.BigInteger(), nullable=False),
        sa.Column('booking_id', sa.String(36), nullable=False),
        sa.Column('seat_count', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('ACTIVE', 'RELEASED', 'EXPIRED',
                    name='reservationstatus', create_type=False),
            nullable=False,
            server_default='ACTIVE'
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['flight_id'], ['flights.id']),
        sa.UniqueConstraint('booking_id', name='uq_seat_reservations_booking_id'),
    )


def downgrade() -> None:
    op.drop_table('seat_reservations')
    op.drop_index('uq_flight_number_date', table_name='flights')
    op.drop_table('flights')
    op.execute("DROP TYPE IF EXISTS reservationstatus")
    op.execute("DROP TYPE IF EXISTS flightstatus")
