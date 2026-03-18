"""Initial migration - bookings table

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
    # Create booking status enum
    booking_status = postgresql.ENUM(
        'CONFIRMED', 'CANCELLED',
        name='bookingstatus'
    )
    booking_status.create(op.get_bind())

    op.create_table(
        'bookings',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('flight_id', sa.BigInteger(), nullable=False),
        sa.Column('passenger_name', sa.String(255), nullable=False),
        sa.Column('passenger_email', sa.String(255), nullable=False),
        sa.Column('seat_count', sa.Integer(), nullable=False),
        sa.Column('total_price', sa.Numeric(10, 2), nullable=False),
        sa.Column(
            'status',
            sa.Enum('CONFIRMED', 'CANCELLED', name='bookingstatus'),
            nullable=False,
            server_default='CONFIRMED',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_bookings_user_id', 'bookings', ['user_id'])
    op.create_index('ix_bookings_flight_id', 'bookings', ['flight_id'])


def downgrade() -> None:
    op.drop_index('ix_bookings_flight_id', table_name='bookings')
    op.drop_index('ix_bookings_user_id', table_name='bookings')
    op.drop_table('bookings')
    op.execute("DROP TYPE IF EXISTS bookingstatus")
