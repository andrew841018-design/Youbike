CREATE TABLE run_status (
    run_id UUID PRIMARY KEY,
    source TEXT NOT NULL CHECK(btrim(source) <> ''),
    scheduled_at TIMESTAMPTZ NOT NULL,
    status TEXT CHECK(status in ('missing','running','succeeded','failed')) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration INTERVAL,
    retry_count INTEGER CHECK(retry_count >= 0) NOT NULL DEFAULT 0,
    error_code TEXT,
    inserted_count INTEGER CHECK(inserted_count >= 0) DEFAULT 0,
    skipped_count INTEGER CHECK(skipped_count >= 0) DEFAULT 0,
    rejected_count INTEGER CHECK(rejected_count >= 0) DEFAULT 0
);