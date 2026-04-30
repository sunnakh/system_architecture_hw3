CREATE TABLE IF NOT EXISTS urls (
    id BIGSERIAL PRIMARY KEY,
    short_code TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    thumb_name TEXT NOT NULL,
    watermark_name TEXT NOT NULL,
    mime TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_urls_short_code
ON urls (short_code);