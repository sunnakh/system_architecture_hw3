import os
import uuid
from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Header,
    HTTPException,
    Request,
)
from fastapi.responses import HTMLResponse
from jinja2 import Template

from . import image_pb2, db, grpc_client
from .idempotency import idempotent
from .ws import router as ws_router, broadcast_view

IMAGES_DIR = Path(os.environ.get("IMAGES_DIR", "./images"))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC = os.environ.get("PUBLIC_BASE_URL", "http://64.226.92.196:8000")

MAX_BYTES = 10 * 1024 * 1024  # 10 MB

app = FastAPI(
    title="Image Pastebin API",
    description="Upload images, get short URLs, watch live view counts.",
    version="1.0.0",
)

app.include_router(ws_router)


@app.post(
    "/api/upload",
    summary="Upload an image and receive a short URL",
    response_description="The short code and the three derived URLs",
)
@idempotent
async def upload(
    request: Request,
    file: UploadFile = File(
        ...,
        description="Image file, max 10 MB"
    ),
    x_request_id: str = Header(
        ...,
        alias="X-Request-ID",
        description="Client-generated UUID for idempotency",
    ),
):
    # 1. Size guard
    body = await file.read(MAX_BYTES + 1)

    if len(body) > MAX_BYTES:
        raise HTTPException(413, "File too large (>10 MB)")

    if file.content_type not in (
        "image/jpeg",
        "image/png",
        "image/webp",
    ):
        raise HTTPException(
            415,
            "Only JPEG, PNG, and WebP are accepted"
        )

    # 2. Persist original bytes
    uid = uuid.uuid4().hex

    orig_path = IMAGES_DIR / f"{uid}_orig"
    orig_path.write_bytes(body)

    # 3. Run three gRPC calls
    compressed = IMAGES_DIR / f"{uid}.jpg"
    thumbnail = IMAGES_DIR / f"{uid}_t.jpg"
    watermark = IMAGES_DIR / f"{uid}_w.jpg"

    grpc_client.process(
        str(orig_path),
        str(compressed),
        image_pb2.COMPRESS
    )

    grpc_client.process(
        str(compressed),
        str(thumbnail),
        image_pb2.THUMBNAIL
    )

    grpc_client.process(
        str(compressed),
        str(watermark),
        image_pb2.WATERMARK
    )

    orig_path.unlink()  # drop uncompressed original

    # 4. Write metadata
    _id, code = await db.insert_url(
        filename=compressed.name,
        thumb=thumbnail.name,
        watermark=watermark.name,
        mime="image/jpeg",
        size=compressed.stat().st_size,
    )

    return {
        "short_code": code,
        "short_url": f"{PUBLIC}/s/{code}",
        "image_url": f"{PUBLIC}/images/{compressed.name}",
        "thumb_url": f"{PUBLIC}/images/{thumbnail.name}",
        "watermark_url": f"{PUBLIC}/images/{watermark.name}",
    }


@app.get(
    "/api/meta/{code}",
    summary="Return metadata for a short code",
)
async def meta(code: str):
    row = await db.get_by_code(code)

    if row is None:
        raise HTTPException(404, "Unknown short code")

    return {
        "short_code": row["short_code"],
        "image_url": f"{PUBLIC}/images/{row['filename']}",
        "thumb_url": f"{PUBLIC}/images/{row['thumb_name']}",
        "created_at": row["created_at"].isoformat(),
        "size_bytes": row["size_bytes"],
    }


VIEW_PAGE = Template("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ code }}</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header>
    <a href="/">&larr; Upload another</a>
  </header>

  <main>
    <img src="/images/{{ filename }}" alt="shared image">
    <p class="views">
      Live views: <span id="views">...</span>
    </p>
  </main>

  <script>
    const code = "{{ code }}";

    const ws = new WebSocket(
      (location.protocol === "https:" ? "wss://" : "ws://") +
      location.host +
      "/ws/views/" +
      code
    );

    ws.onmessage = (e) => {
      document.getElementById("views").textContent =
        JSON.parse(e.data).views;
    };
  </script>
</body>
</html>
""")


@app.get(
    "/s/{code}",
    response_class=HTMLResponse,
    summary="Human-facing short URL landing page",
)
async def view(code: str):
    row = await db.get_by_code(code)

    if row is None:
        raise HTTPException(404, "Unknown short code")

    await broadcast_view(code)

    return HTMLResponse(
        VIEW_PAGE.render(
            code=code,
            filename=row["filename"],
        )
    )
