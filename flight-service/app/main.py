import asyncio
import logging

import grpc
import uvicorn

from app import flight_pb2_grpc
from app.admin import app as admin_app
from app.config import settings
from app.servicer import FlightServicer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def serve_grpc():
    server = grpc.aio.server()
    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServicer(), server)
    listen_addr = f"[::]:{settings.grpc_port}"
    server.add_insecure_port(listen_addr)
    await server.start()
    logger.info(f"gRPC server started on port {settings.grpc_port}")
    await server.wait_for_termination()


async def serve_http():
    config = uvicorn.Config(admin_app, host="0.0.0.0", port=8001, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(serve_grpc(), serve_http())


if __name__ == "__main__":
    asyncio.run(main())
