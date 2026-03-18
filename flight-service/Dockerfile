FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY flight-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY proto /proto
RUN mkdir -p ./app
RUN python -m grpc_tools.protoc -I/proto --python_out=./app --grpc_python_out=./app /proto/flight.proto
RUN sed -i 's/^import flight_pb2 as flight__pb2/from app import flight_pb2 as flight__pb2/' ./app/flight_pb2_grpc.py
COPY flight-service/ .
RUN sed -i 's/\r$//' start.sh
RUN chmod +x start.sh
CMD ["./start.sh"]
