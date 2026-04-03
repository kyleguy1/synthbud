# synthbud

Generate and browse copyright-friendly synth sounds and presets.

The app currently has two main areas:
- sound search backed by Freesound
- preset search with local banks plus online discovery/indexing

## What preset sources mean

On the `/presets` page you will see three sources:
- `Local Library`: presets already imported into your own database from folders on disk
- `Indexed Online`: PresetShare metadata synced into your database for faster, larger in-app search
- `Browse Online`: live PresetShare browsing without syncing first

Important defaults:
- the presets page defaults to `Local Library`
- `Local Library` will be empty until you add preset files and run the local preset ingestor
- `Indexed Online` will be empty until you run a sync
- `Browse Online` works out of the box as long as the backend has internet access
- the default preset page size is `20`, and the UI lets you raise it to `50` or `100`

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

Notes:
- the Docker Postgres container is exposed on `localhost:5433`
- the default backend `.env.example` already points SQLAlchemy at `localhost:5433`

## Frontend setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

- App: `http://localhost:5173`

## One-step startup

```bash
./scripts/dev.sh
```

The script now:
- starts Docker Postgres if available
- reuses an already healthy backend on `localhost:8000`
- clears a stale repo backend process that is blocking port `8000`
- stops with a clear message if some unrelated process is using `8000`

## Local preset banks

Local preset banks are folder-based. A bank maps to the existing `PresetPack` model in the database.

Default local preset root:
- `backend/data/presets/local`

Canonical folder layout:

```text
backend/data/presets/local/
  serum/
    My Bank/
      Lead 01.fxp
      Pads/
        Warm Pad 01.fxp
```

Rules:
- first folder under the root = synth
- second folder = bank name
- deeper folders are folded into search tags, not treated as separate banks
- files directly under `<synth>/` are ingested into an `Unsorted` bank

Current local parser support:
- Serum only
- supported file extensions: `.fxp`, `.serumpreset`

Import local presets:

```bash
cd backend
source .venv/bin/activate
python -m app.ingestion.presets.local_library_ingestor
```

The local preset ingestor is safe to rerun. It is designed to be idempotent and will reuse existing imported rows when possible.

If you want to use a different local preset folder, set `SYNTHBUD_PRESET_LOCAL_ROOTS` in `backend/.env` as a JSON list, for example:

```env
SYNTHBUD_PRESET_LOCAL_ROOTS=["/absolute/path/to/my/presets"]
```

## Online preset discovery

### Browse Online

`Browse Online` uses live PresetShare scraping. It does not require a separate API key.

Use it when you want:
- zero setup beyond a working backend internet connection
- live results from PresetShare
- filters like synth, genre, and sound type without syncing first

### Indexed Online

`Indexed Online` syncs PresetShare metadata into your local database so searching and paging scale better than live scraping alone.

Use it when you want:
- larger searchable preset coverage inside the app
- database-backed paging and filtering
- to avoid scraping live for every result page

You can sync from the app by opening `/presets`, choosing `Indexed Online`, and clicking `Sync 10 pages`.

You can also sync from the API:

```bash
curl -X POST "http://localhost:8000/api/presets/sync?source=presetshare-index&max_pages=10"
```

Notes:
- `max_pages` controls how many PresetShare pages are indexed in that run
- synced online entries are metadata records, not downloaded preset files
- after syncing, search them in the app with source set to `Indexed Online`

## Optional data ingestion

```bash
cd backend
source .venv/bin/activate
python -m app.ingestion.freesound_ingestor
python -m app.ingestion.feature_extractor
python -m app.ingestion.presets.public_catalog_ingestor
```

## Minimal troubleshooting

- `npm: command not found` -> install Node.js, then reopen terminal.
- `/presets` is empty -> this is usually expected if the source is `Local Library` and you have not imported any local preset banks yet.
- `Indexed Online` is empty -> run a sync from the UI or `POST /api/presets/sync`.
- `Browse Online` shows an error or no results -> make sure the backend can reach the public internet.
- `type "ingestionstatusenum" already exists` during migration:

```bash
docker exec backend-postgres-1 psql -U postgres -d synthbud -c "DROP TYPE IF EXISTS ingestionstatusenum CASCADE;"
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
```
