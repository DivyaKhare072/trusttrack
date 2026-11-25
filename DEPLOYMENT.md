# Deployment

## Neon

Create a PostgreSQL database and set `DATABASE_URL` to the Neon connection string. Neon PostgreSQL URLs use `postgresql://` or `postgresql+psycopg://`; SQLAlchemy generally accepts Neon URLs, but add `psycopg[binary]` if required.

## Render

Build: `pip install -r backend/requirements.txt`
Start: `cd backend && gunicorn app:app`

Environment variables:
- `SECRET_KEY`: cryptographically random value
- `DATABASE_URL`: Neon PostgreSQL URL
- `FRONTEND_ORIGINS`: exact deployed frontend origin(s)
- `COOKIE_SECURE=true`
- `FLASK_ENV=production`
- `SMS_PROVIDER`: `development` or an implemented production provider

## Frontend

Deploy `frontend/` unchanged. Update `API` in `frontend/js/app.js` to the deployed Render API origin plus `/api`.

## Database migrations

Use Flask-Migrate in the backend. The initial migration should create tables without deleting existing tables or records. Never use destructive reset commands against production.
