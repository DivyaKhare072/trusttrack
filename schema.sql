-- TrustTrack normalized PostgreSQL schema. Flask-SQLAlchemy creates tables automatically in development.
-- Production migrations should be applied by Flask-Migrate; never recreate existing records.
CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL CHECK(role IN ('customer','dispatcher','agent','administrator')), active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS parcels (id SERIAL PRIMARY KEY, tracking_id VARCHAR(24) UNIQUE NOT NULL, customer_id INTEGER NOT NULL REFERENCES users(id), status VARCHAR(30) NOT NULL DEFAULT 'BOOKED', qr_token VARCHAR(64) UNIQUE NOT NULL, weight_kg DOUBLE PRECISION NOT NULL CHECK(weight_kg > 0), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_parcels_tracking ON parcels(tracking_id);
CREATE TABLE IF NOT EXISTS custody_events (id SERIAL PRIMARY KEY, parcel_id INTEGER NOT NULL REFERENCES parcels(id), previous_status VARCHAR(30), new_status VARCHAR(30) NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), previous_hash VARCHAR(64), event_hash VARCHAR(64) NOT NULL, timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_custody_parcel ON custody_events(parcel_id, id);
