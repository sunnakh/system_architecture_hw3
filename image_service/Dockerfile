FROM python:3.11-slim

# Copy the uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN uv pip install --system --no-cache -r requirements.txt

COPY image.proto image_pb2.py image_pb2_grpc.py server.py ./

EXPOSE 50051

CMD ["python", "server.py"]
