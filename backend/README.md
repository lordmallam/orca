# Backend Services

Python backend services for the AIS Viewer system.

## Services

1. **ingest_service.py** - Main ingestion service (WebSocket → PostgreSQL)
2. **api_service.py** - FastAPI REST API for vessel queries

## Setup

1. Install dependencies:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
# Edit .env and add your AISSTREAM_API_KEY
```

3. Test aisstream.io connection:

```bash
python test_aisstream.py
```

## Requirements

- Python 3.11+
- PostgreSQL 15+ with PostGIS (for ingest and API services)
- AIS Stream API key (https://aisstream.io)

## Environment Variables

See `.env.example` for all configuration options.
