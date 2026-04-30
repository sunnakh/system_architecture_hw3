# Image Pastebin

A containerized image-sharing platform with short links, live view counters, and asynchronous image processing.

## What this project does

- Uploads an image (JPEG/PNG/WebP, max 10 MB).
- Creates three derived outputs:
- Compressed JPEG
- Thumbnail JPEG (max 256x256)
- Watermarked JPEG
- Stores metadata in PostgreSQL and returns a short URL.
- Serves processed image files via Nginx.
- Tracks and broadcasts live view counts over WebSocket.
- Guarantees safe request retries using idempotency keys.

## Tech stack (with role of each technology)

- FastAPI: backend HTTP API and WebSocket endpoint.
- Uvicorn: ASGI server for FastAPI.
- Redis:
- Pub/sub for cross-worker WebSocket fan-out.
- Atomic counters for view tracking.
- Idempotency key store (`PENDING` + cached result).
- PostgreSQL + asyncpg: persistent metadata storage.
- gRPC + Protocol Buffers: backend-to-image-service RPC contract.
- Pillow: actual image transformation (compress, thumbnail, watermark).
- Nginx:
- Reverse proxy for frontend/backend routes.
- WebSocket upgrade handling.
- Direct static serving for `/images/*`.
- Docker + Docker Compose: local and server deployment orchestration.

## Architecture

```text
Browser
	|
	|  GET /, POST /api/upload, GET /s/{code}, WS /ws/views/{code}
	v
Nginx (entrypoint)
	|-- /           -> frontend (static app)
	|-- /api, /s    -> backend (FastAPI)
	|-- /ws         -> backend (WebSocket)
	|-- /images/*   -> shared volume (direct file serving)

backend (FastAPI)
	|-- PostgreSQL (metadata)
	|-- Redis (views + pub/sub + idempotency)
	|-- gRPC -> image_service (Pillow operations)

image_service writes processed files to shared images volume
Nginx serves those files directly
```

## Repository layout

```text
backend/        FastAPI app, DB access, idempotency, Redis WS pub/sub, gRPC client
frontend/       Static upload UI
image_service/  gRPC image processing microservice
nginx/          Reverse-proxy and static-serving config
postgres/       DB schema bootstrap SQL
images/         Local image directory (mounted via Docker volume)
```

## Quick start (Docker Compose)

### 1. Prerequisites

- Docker Engine + Docker Compose plugin
- Open port: `80` (database and Redis are internal to the Compose network)

### 2. Run

```bash
docker compose up --build -d
```

### 3. Verify services

```bash
docker compose ps
docker compose logs -f backend image_service nginx
```

### 4. Open app

- UI: `http://localhost/`
- API docs: `http://localhost/docs`
- ReDoc: `http://localhost/redoc`

## End-to-end request flow

1. Frontend posts `multipart/form-data` to `POST /api/upload` with header `X-Request-ID`.
2. Backend idempotency middleware reserves `idem:{X-Request-ID}` in Redis with `PENDING`.
3. Backend validates type/size and stores original bytes on shared images volume.
4. Backend calls image service over gRPC 3 times:
- `COMPRESS`
- `THUMBNAIL`
- `WATERMARK`
5. Backend inserts metadata in PostgreSQL and generates a base62 short code.
6. Backend caches JSON response under the same idempotency key and returns URLs.
7. User opens short URL `/s/{code}`; backend increments Redis counter and publishes to `chan:{code}`.
8. WebSocket clients subscribed on `/ws/views/{code}` receive live counter updates.

## API and WebSocket contract

### `POST /api/upload`

- Headers:
- `X-Request-ID: <uuid>` (required)
- Body:
- `file` (JPEG/PNG/WebP, <= 10 MB)
- Success response:

```json
{
	"short_code": "000a",
	"short_url": "http://localhost/s/000a",
	"image_url": "http://localhost/images/abc.jpg",
	"thumb_url": "http://localhost/images/abc_t.jpg",
	"watermark_url": "http://localhost/images/abc_w.jpg"
}
```

### `GET /api/meta/{code}`

- Returns metadata for a short code.

### `GET /s/{code}`

- Renders image view page and triggers one view increment + broadcast.

### `WS /ws/views/{code}`

- On connect: sends current count immediately.
- Then streams messages like:

```json
{"views": 42}
```

## Why Redis pub/sub is required (multi-worker correctness)

If Uvicorn runs with multiple workers, in-memory socket registries are isolated per process. A request handled by worker B cannot access sockets held by worker A. Redis pub/sub solves this by broadcasting view events through a shared broker so each worker can fan out updates to its own local sockets.

## Data model

`urls` table:

- `id BIGSERIAL PRIMARY KEY`
- `short_code TEXT UNIQUE`
- `filename TEXT`
- `thumb_name TEXT`
- `watermark_name TEXT`
- `mime TEXT`
- `size_bytes BIGINT`
- `created_at TIMESTAMPTZ DEFAULT NOW()`

Index:

- `idx_urls_short_code` on `short_code`

## gRPC contract

`ImageService.ProcessImage(ProcessRequest) -> ProcessResponse`

Operations:

- `COMPRESS`: lossy JPEG recompression (quality ~70)
- `THUMBNAIL`: resize longest side to 256 px
- `WATERMARK`: stamp "Image Pastebin" bottom-right

## Nginx routing strategy

- `/api/*`, `/s/*`, docs endpoints -> backend
- `/ws/*` -> backend with upgrade headers
- `/images/*` -> direct static serving from shared volume
- `/` -> frontend static site

Direct image serving keeps backend free for dynamic workloads and improves throughput and latency for static bytes.

## Idempotency behavior

For `X-Request-ID`:

1. First request sets Redis key to `PENDING` (short TTL).
2. Duplicate in-flight requests wait briefly for final result.
3. When done, final JSON is cached (24h TTL).
4. If processing fails, the key is deleted so client can retry safely.

This prevents duplicate DB writes and duplicate image processing under retries or unstable networks.

## Configuration

Backend environment variables:

- `DATABASE_URL` (PostgreSQL DSN)
- `REDIS_URL` (Redis DSN)
- `IMAGE_SERVICE_ADDR` (gRPC target, default `image_service:50051` in Compose)
- `IMAGES_DIR` (shared path where processed images are written)
- `PUBLIC_BASE_URL` (base URL used in returned links)

## Local development without Docker (optional)

You need running PostgreSQL, Redis, and image service.

### Backend

```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL='postgresql://postgres:password@localhost:5432/pastebin'
export REDIS_URL='redis://localhost:6379/0'
export IMAGE_SERVICE_ADDR='localhost:50051'
export IMAGES_DIR='./images'
export PUBLIC_BASE_URL='http://localhost:8000'
uvicorn app.main:app --reload --port 8000
```

### Image service

```bash
cd image_service
pip install -r requirements.txt
python server.py
```

### Frontend

Serve `frontend/` as static files (Nginx or any static server) and proxy `/api`, `/s`, `/ws` to backend.

## Operations and troubleshooting

- Backend fails at startup:
- Check `DATABASE_URL`, `REDIS_URL`, and DB/Redis container health.
- Upload returns `409 Request still in progress`:
- Same idempotency key is still processing; retry after a short delay.
- No live view updates:
- Verify Redis reachable and WebSocket route `/ws/views/{code}` proxied with upgrade headers.
- Image not found under `/images/*`:
- Confirm shared volume is mounted in both `backend`, `image_service`, and `nginx`.

## Security and production notes

- Place TLS termination in front of Nginx (or enable HTTPS directly).
- Restrict upload MIME/type checks further with content sniffing if needed.
- Add auth/rate-limiting for public deployments.
- Consider object storage (S3-compatible) for large-scale image persistence.
- Replace default credentials and pin/scan container images in CI.

## License

MIT
