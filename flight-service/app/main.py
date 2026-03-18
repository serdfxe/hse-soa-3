import asyncio
import logging

import grpc

from app import flight_pb2_grpc
from app.config import settings
from app.servicer import FlightServicer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def serve():
    server = grpc.aio.server()
    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServicer(), server)
    listen_addr = f"[::]:{settings.grpc_port}"
    server.add_insecure_port(listen_addr)
    await server.start()
    logger.info(f"gRPC server started on port {settings.grpc_port}")
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
