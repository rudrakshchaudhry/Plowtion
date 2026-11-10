# Plowtion

Plowtion is a small full-stack farming assistant. Given soil and climate readings it
recommends a crop with a scikit-learn model; given a crop it reports the typical growing
conditions from the training data and generates an approximate planting-to-harvest
schedule. It also exposes a keyless weather forecast and an optional chatbot.

Built as a team project. This repository has been updated so that everything below runs
locally without the original cloud services.

## Architecture

```
frontend/   Next.js 15 (App Router) UI: home form, crop guide, marketplace, profile.
            Optional Google sign-in via Auth.js (NextAuth v5).
backend/    Flask API
  app.py            routes (create_app factory)
  train.py          trains the crop recommender, writes model/ artifacts
  plowtion/         config, model wrapper, schedule rules, weather + chat clients, storage
  dataset/          Crop_recommendation.csv (2,200 rows, 22 crops), zip-code.csv (soil by US ZIP)
  tests/            pytest suite (offline)
model/      crop_model.joblib (trained pipeline + per-crop profiles), metrics.json
docker-compose.yml  frontend + backend + local MongoDB
```

Request flow on the home page: ZIP code -> `GET /get-soil-by-zip/<zip>` (soil N, P, K, pH
from `zip-code.csv`) -> `POST /predict-conditions` (typical temperature, humidity and
rainfall for the selected crop, soil-range check, and a schedule).

### API

| Method | Path | Purpose | Needs |
|---|---|---|---|
| GET | `/health` | Model, database, chat status | - |
| POST | `/predict` | Recommend a crop from `N, P, K, temperature, humidity, ph, rainfall` | - |
| GET | `/crops` | Supported crop names | - |
| POST | `/schedule` | Schedule for `{"crop": "maize", "start_date": "YYYY-MM-DD"}` | - |
| GET | `/weather?lat=..&lon=..&days=7` | Current conditions and daily forecast (Open-Meteo) | Internet |
| POST | `/chat` | `{"message": "..."}`; returns 503 when no LLM key is set | LLM API key |
| GET | `/get-soil-by-zip/<zip>` | Soil readings for a US ZIP code | - |
| POST | `/predict-conditions` | Growing conditions and schedule for a crop + soil readings | - (saves to MongoDB if configured) |
| POST/GET/DELETE | `/push-user`, `/get-users`, `/delete-user/<id>`, `/get-user-conditions`, `/get-user-condition/<id>` | Stored users and past results | MongoDB + `ADMIN_TOKEN` |

`/predict` validates every field and returns 400 with per-field details for missing,
non-numeric or out-of-range values (for example pH outside 0-14 or humidity outside 0-100).

The user-data endpoints require `Authorization: Bearer $ADMIN_TOKEN` and are disabled
when `ADMIN_TOKEN` is unset. The other endpoints are open; run the API on a trusted
network or behind an authenticating proxy, and add rate limiting before exposing it.

## What works locally and what needs external services

| Feature | Local, no accounts | Notes |
|---|---|---|
| Crop recommendation (`/predict`) | Yes | Local scikit-learn model. SageMaker is used only if `SAGEMAKER_ENDPOINT` is set (requires `pip install boto3` and AWS credentials; that path is not tested here). |
| Growing conditions + schedule | Yes | Conditions are per-crop averages from the dataset; the schedule is rule-based and approximate. |
| Soil lookup by ZIP code | Yes | Static CSV bundled in the repo. |
| Weather | Yes, with internet access | Open-Meteo, no API key. API only (`/weather`); the frontend does not display it yet. Returns 503 if the service is unreachable. |
| Storage of users / results | Yes, with MongoDB | `docker compose` starts a local `mongo`; or set `MONGO_URI`. Without it, storage endpoints return 503 and everything else works. |
| Chatbot | No | Needs an OpenAI-compatible API key (`LLM_API_KEY`, default provider Perplexity). Without it `/chat` returns 503 "not configured". The frontend has no chat UI. |
| Google sign-in | No | Needs your own Google OAuth client (`AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `AUTH_SECRET`). Without them the sign-in buttons are hidden and the app runs signed-out. |
| Marketplace | Display only | Static product list; there is no checkout, payment or seller flow. |
| Profile page | Display only | Shows the signed-in user's name and photo; the rest is placeholder content. |

## Quick start (local, no Docker)

Requires Python 3.12 and Node.js 22.

1. Clone and create a virtual environment:
   ```bash
   git clone https://github.com/rudrakshchaudhry/Plowtion.git && cd Plowtion
   python3 -m venv .venv && source .venv/bin/activate
   ```
2. Install backend dependencies and run the tests (offline, under 10 seconds):
   ```bash
   pip install -r backend/requirements-dev.txt
   (cd backend && pytest -q)
   ```
3. Optionally retrain the model (about 3 seconds; overwrites `model/crop_model.joblib` and `model/metrics.json`):
   ```bash
   python backend/train.py
   ```
4. Start the API and try it:
   ```bash
   python backend/app.py        # http://localhost:5001
   curl localhost:5001/health
   curl -X POST localhost:5001/predict -H 'Content-Type: application/json' \
     -d '{"N":90,"P":42,"K":43,"temperature":20.88,"humidity":82.0,"ph":6.5,"rainfall":202.9}'
   ```
5. In a second terminal, build and start the frontend:
   ```bash
   cd frontend && cp .env.example .env.local
   npm ci && npm run build && npm start   # http://localhost:3000
   ```

Configuration is read from environment variables only. Copy `.env.example` to `.env`
(backend, loaded by `python backend/app.py`) and `frontend/.env.example` to
`frontend/.env.local`; every value is optional.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts MongoDB, the API on port 5001 and the frontend on port 3000. The compose file
has been validated with `docker compose config`; the images were not built as part of this
update.

## Model

`backend/train.py` trains a `Pipeline(StandardScaler, RandomForestClassifier)` on the seven
features `N, P, K, temperature, humidity, ph, rainfall` to predict one of 22 crops, and
evaluates it with 5-fold stratified cross-validation (shuffle, `random_state=42`). It is
deterministic: re-running it reproduces the numbers below. Current results from
`model/metrics.json` (model version 2.0.0, scikit-learn 1.9.1, 2,200 rows):

| Metric | Mean | Std |
|---|---|---|
| Accuracy | 0.9950 | 0.0022 |
| Macro-F1 | 0.9950 | 0.0022 |

The dataset is small and clean, with 100 rows per crop and well-separated classes, so these
scores say little about performance on real field measurements.

## Tests and CI

`backend/tests` covers the health endpoint, prediction (happy path and validation errors),
schedule generation, the weather client (success, timeout, error, malformed payload) with
mocked HTTP, the chatbot (not configured, mocked provider response and provider error), and
storage via `mongomock`. A fixture blocks
all network access during tests.

GitHub Actions (`.github/workflows/ci.yml`) runs the backend tests, a training sanity check
(fails below 0.95 CV accuracy) and the frontend production build with placeholder
environment values.

## License

MIT. See [LICENSE](LICENSE).
