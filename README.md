# AIS Viewer System

A real-time vessel tracking system that ingests AIS (Automatic Identification System) data from aisstream.io and displays vessel positions on a mobile map application.

![Architecture](https://img.shields.io/badge/Architecture-Simplified-green)
![Backend](https://img.shields.io/badge/Backend-Python-blue)
![Frontend](https://img.shields.io/badge/Frontend-React%20Native-61DAFB)
![Database](https://img.shields.io/badge/Database-PostgreSQL%20%2B%20PostGIS-336791)

## Architecture

```
┌─────────────────┐
│  aisstream.io   │ WebSocket Stream
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Ingest Service  │ Python + In-memory Queue
│  (WebSocket)    │ Batch UPSERT every 2s
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │ PostGIS + Geohash Indexes
│   + PostGIS     │ UPSERT Pattern (1 row/vessel)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   API Service   │ FastAPI REST + Delta Queries
│    (FastAPI)    │ Geohash-based viewport filtering
└────────┬────────┘
         │
         ▼ HTTP Poll (10s)
┌─────────────────┐
│  Mobile App     │ React Native + Mapbox
│ (React Native)  │ Zoom >= 12 enforcement
└─────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for mobile app)
- [AIS Stream API key](https://aisstream.io) (free)
- [Mapbox access token](https://account.mapbox.com/access-tokens/) (free tier available)

### One-Command Setup

```bash
git clone <repository-url>
cd orca
./quick-start.sh
```

This will:

1. Start PostgreSQL with PostGIS
2. Create Python virtual environment
3. Install backend dependencies

### Manual Setup

#### 1. Start Database

```bash
docker-compose up -d
```

#### 2. Configure Backend

```bash
cd backend
cp .env.example .env
# Edit .env and add your AISSTREAM_API_KEY
```

#### 3. Install Backend Dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 4. Start Backend Services

```bash
# Terminal 1: Ingest Service
python ingest_service.py

# Terminal 2: API Service
python api_service.py
```

#### 5. Setup Mobile App

```bash
cd mobile

# Install dependencies (if npm cache issues, see mobile/README.md)
npm install

# Configure
cat > .env << EOF
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
EXPO_PUBLIC_MAPBOX_TOKEN=your_mapbox_token_here
EOF

# Start app
npm start
```

Then press `i` for iOS or `a` for Android.

## Project Structure

```
orca/
├── backend/                     # Python backend services
│   ├── ingest_service.py       # WebSocket → PostgreSQL ingestion
│   ├── api_service.py          # FastAPI REST API
│   ├── config.py               # Configuration management
│   ├── init.sql                # Database schema
│   ├── requirements.txt        # Python dependencies
├── mobile/                      # React Native mobile app
│   ├── src/
│   │   ├── components/
│   │   │   └── VesselMap.tsx  # Main map component
│   │   ├── contexts/
│   │   │   └── VesselContext.tsx  # React Context state
│   │   ├── services/
│   │   │   └── VesselApiService.ts  # HTTP polling client
│   │   ├── types.ts           # TypeScript types
│   │   └── config.ts          # App configuration
│   ├── App.tsx                # Main app component
│   └── package.json
├── docker-compose.yml          # PostgreSQL + PostGIS
├── quick-start.sh              # Quick setup script
├── README.md                   # This file
```

## Key Features

### Backend

- **WebSocket Ingestion**: Connects to aisstream.io and processes PositionReport messages
- **Batch UPSERT**: Efficient database writes (100 records / 2 seconds)
- **Auto-cleanup**: Removes stale vessels (> 2 minutes old)
- **Delta Updates**: API returns only changed vessels since last query

### Mobile App

- **10-second Polling**: HTTP GET requests every 10 seconds
- **Zoom Enforcement**: Only shows vessels at zoom level >= 12
- **Course Indicators**: Vessel markers rotated to show direction
- **React Context**: Built-in state management (no external dependencies)
- **Delta Support**: Reduces bandwidth by fetching only updates

## Performance Targets

| Metric             | Target         | How It's Achieved                   |
| ------------------ | -------------- | ----------------------------------- |
| End-to-end latency | < 15 seconds   | 10s poll + 2s batch + 3s processing |
| API response time  | < 200ms        | Geohash indexes + UPSERT pattern    |
| Database query     | < 100ms        | PostGIS GIST index + geohash B-tree |
| Ingest rate        | 3,000 msgs/sec | In-memory queue + batch processing  |
| Concurrent users   | 1,000+         | Stateless API + connection pooling  |
| Database size      | ~10 MB         | 30k vessels × 300 bytes (UPSERT)    |

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-08T12:00:00Z",
  "database": "connected",
  "vessels_count": 12345
}
```

## Technology Stack

| Component    | Technology              | Why                                  |
| ------------ | ----------------------- | ------------------------------------ |
| **Ingest**   | Python 3.11             | WebSocket client, async processing   |
| **API**      | FastAPI                 | High-performance, auto-documentation |
| **Database** | PostgreSQL 15 + PostGIS | Geospatial queries, UPSERT pattern   |
| **Mobile**   | React Native + Expo     | Cross-platform, Mapbox SDK           |
| **Map**      | Mapbox GL               | GPU-accelerated rendering            |
| **State**    | React Context API       | Built-in, no dependencies            |

## Documentation

- [README.md](README.md) - This file (overview & quick start)
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment guide
- [TESTING.md](TESTING.md) - Testing & performance optimization
- [backend/README.md](backend/README.md) - Backend services details
- [mobile/README.md](mobile/README.md) - Mobile app setup & troubleshooting

## Troubleshooting

### Ingest service not receiving data

1. Check `AISSTREAM_API_KEY` is valid in backend/.env
2. Check logs: `docker logs ais_ingest_service`
3. Test connection: `python backend/test_aisstream.py`

### API returns no vessels

1. Verify ingest service is running
2. Check database: `SELECT COUNT(*) FROM vessels;`
3. Ensure zoom level >= 12 in API request

### Mobile app shows no vessels

1. Zoom in to level 12 or higher
2. Check `EXPO_PUBLIC_API_BASE_URL` in mobile/.env
3. For physical device, use ngrok: `ngrok http 8000`

### npm install issues

See [mobile/README.md](mobile/README.md) for npm cache fixes.

## Demo Video

To create a demo video:

1. Start all services (database, ingest, API)
2. Open mobile app
3. Show:
   - Zoom out (no vessels, warning message)
   - Zoom in to level 12+ (vessels appear)
   - Real-time updates (vessels moving)
   - Viewport panning (new vessels load)
   - Status bar (vessel count, zoom level)
