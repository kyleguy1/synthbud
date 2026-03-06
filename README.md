# synthbud

Personal project for generating/scraping free synth sounds (leads, plucks, melodies) that are copyright friendly. The backend ingests CC0/CC-BY sounds from the [Freesound API](https://freesound.org/docs/api/authentication.html#token-authentication), stores them in Postgres, extracts audio features, and exposes a REST API for search and filtering.

---

## Backend (Python + FastAPI + Postgres)

### Prerequisites

- **Python 3.10+**
- **PostgreSQL** (running locally or remotely)
- A **Freesound API token** from [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply)

### 1. Create the database

Create a Postgres database (e.g. named `synthbud`):

```bash
createdb synthbud
```

Or with `psql`:

```sql
CREATE DATABASE synthbud;
```

### 2. Set up the Python environment

From the project root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example env file and set your values:

```bash
cp .env.example .env
```

Edit `.env`:

- **`SYNTHBUD_DATABASE_URL`** – Postgres URL. Default:
  `postgresql+psycopg2://postgres:postgres@localhost:5432/synthbud`
- **`SYNTHBUD_FREESOUND_API_TOKEN`** – Your Freesound API key (token authentication).

Optional (defaults are fine for local dev):

- `SYNTHBUD_APP_NAME`, `SYNTHBUD_ENVIRONMENT`
- `SYNTHBUD_DEFAULT_PAGE_SIZE`, `SYNTHBUD_MAX_PAGE_SIZE`
- `SYNTHBUD_FEATURE_SAMPLE_RATE`, `SYNTHBUD_FEATURE_BATCH_SIZE`

### 4. Run database migrations

From the **project root** (so that `backend/alembic.ini` and `backend/alembic` are found):

```bash
cd /path/to/synthbud
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
```

Or from inside `backend` (with `alembic.ini` in the same directory if you have a copy there, or using the path above from root).

### 5. Start the API server

From the **backend** directory:

```bash
cd backend
python -m app
```

The API will be at **http://localhost:8000**.

- **OpenAPI docs**: http://localhost:8000/api/docs  
- **Health check**: http://localhost:8000/api/health/

### 6. (Optional) Ingest sounds and extract features

Populate the database with CC0/CC-BY synth-related sounds from Freesound:

```bash
cd backend
python -m app.ingestion.freesound_ingestor
```

Then compute audio features (brightness, loudness, BPM, etc.) for previews:

```bash
python -m app.ingestion.feature_extractor
```

You can run the ingestor and feature extractor periodically (e.g. via cron or a scheduler). The API will serve and filter sounds from the data already in Postgres.

### Backend API overview

| Endpoint | Description |
|----------|-------------|
| `GET /api/health/` | Health check and DB connectivity |
| `GET /api/sounds` | Paginated sound list with filters (q, tags, license, duration, brightness, bpm, key, is_loop) |
| `GET /api/sounds/{id}` | Full sound metadata and features |
| `GET /api/meta/tags` | Top tags for filter chips |
| `GET /api/meta/licenses` | Allowed license labels/URLs |

---

## Frontend (React/Vite)

*To be added.* A simple UI to browse, filter, and audition sounds will connect to the backend API above.
