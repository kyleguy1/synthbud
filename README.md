# synthbud

Generate and browse copyright-friendly synth sounds (CC0/CC-BY).

## Prerequisites

- Python 3.10+
- Node.js (includes `npm`)
- Docker (optional, for local Postgres)
- Freesound API token: [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply)

## Backend setup

From project root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `SYNTHBUD_FREESOUND_API_TOKEN` in `backend/.env`.

Start Postgres (Docker):

```bash
cd backend
docker compose up -d
```

Run migrations (from project root):

```bash
cd /path/to/synthbud
source backend/.venv/bin/activate
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
```

Run backend API:

```bash
cd backend
source .venv/bin/activate
python -m app
```

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/api/docs`

## Frontend setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

- App: `http://localhost:5173`

## Optional data ingestion

```bash
cd backend
source .venv/bin/activate
python -m app.ingestion.freesound_ingestor
python -m app.ingestion.feature_extractor
```

## Minimal troubleshooting

- `npm: command not found` -> install Node.js, then reopen terminal.
- `type "ingestionstatusenum" already exists` during migration:

```bash
docker exec backend-postgres-1 psql -U postgres -d synthbud -c "DROP TYPE IF EXISTS ingestionstatusenum CASCADE;"
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
```
