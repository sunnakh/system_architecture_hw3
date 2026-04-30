# Image Pastebin

Image Pastebin is a containerized image-sharing system with short links, live view counters, and asynchronous image processing. It is designed as a small microservice stack that is easy to run locally with Docker Compose.

## Highlights

- Uploads JPEG, PNG, or WebP images up to 10 MB.
- Produces three derived files: compressed JPEG, thumbnail (max 256x256), and watermark.
- Generates base62 short URLs and stores metadata in PostgreSQL.
- Streams live view counts over WebSockets using Redis pub/sub.
- Uses idempotency keys to make retries safe.

## Architecture

```
Browser
   |  /, /api/*, /s/*, /ws/*
   v
Nginx
   |-- /            -> frontend (static app)
   |-- /api, /s     -> backend (FastAPI)
   |-- /ws          -> backend (WebSocket)
   |-- /images/*    -> shared volume (static files)
   v
backend (FastAPI) -> PostgreSQL, Redis, gRPC -> image_service (Pillow)
```

## Repository layout

```
backend/        FastAPI app, DB access, Redis idempotency, gRPC client
frontend/       Static upload UI
image_service/  gRPC image processing service
nginx/          Reverse proxy and static routing
postgres/       DB schema bootstrap
```

## Quick start

### Prerequisites

- Docker and Docker Compose
- Port 80 available on your machine

### Run

```bash
docker compose up --build -d
```

### Verify

```bash
docker compose ps
docker compose logs -f backend image_service nginx
```

### Open

- UI: http://localhost/
- API docs: http://localhost/docs
- ReDoc: http://localhost/redoc

## API overview

- POST /api/upload
  - Headers: X-Request-ID: <uuid>
  - Body: multipart form field `file`
  - Returns short URL and derived image URLs
- GET /api/meta/{code}
  - Returns metadata for the short code
- GET /s/{code}
  - Renders the view page and increments the view counter
- WS /ws/views/{code}
  - Streams JSON updates like {"views": 42}

## Configuration

Backend environment variables:

- DATABASE_URL
- REDIS_URL
- IMAGE_SERVICE_ADDR
- IMAGES_DIR
- PUBLIC_BASE_URL

## Notes

- Redis pub/sub is required for live view updates across multiple backend workers.
- Idempotency keys prevent duplicate processing when clients retry uploads.

## License

MIT
