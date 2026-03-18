#!/bin/bash
set -e
echo "Running migrations..."
alembic upgrade head
echo "Starting gRPC server..."
exec python -m app.main
