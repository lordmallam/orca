"""
AIS API Service

FastAPI REST API for querying vessel positions.

Endpoints:
- GET /api/vessels - Query vessels in viewport with delta support
- GET /health - Health check

Features:
- Viewport queries using geohash filtering
- Delta updates (only return vessels changed since lastUpdateTime)
- Fresh vessel filtering (only vessels updated in last 2 minutes)
- CORS enabled for mobile app
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import pygeohash as pgh
import logging
from config import settings


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

db_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""

    global db_pool
    try:
        database_url = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        db_pool = pool.SimpleConnectionPool(1, 20, database_url)
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise

    yield

    if db_pool:
        db_pool.closeall()
        logger.info("Database connection pool closed")


app = FastAPI(
    title="ORCA - AIS Vessel Tracker API",
    description="REST API for querying vessel positions",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Vessel(BaseModel):
    """Vessel position data model."""

    mmsi: int
    latitude: float
    longitude: float
    course: Optional[float] = None
    speed: Optional[float] = None
    ship_type: Optional[int] = None
    last_updated: str = Field(..., description="ISO 8601 timestamp")


class VesselsResponse(BaseModel):
    """API response model."""

    vessels: List[Vessel]
    server_time: str = Field(..., description="ISO 8601 timestamp")
    count: int
    is_delta: bool = Field(
        default=False, description="Whether this is a delta response"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    database: str
    vessels_count: Optional[int] = None


def get_db_connection():
    """Get a database connection from the pool."""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
    return db_pool.getconn()


def return_db_connection(conn):
    """Return a database connection to the pool."""
    if db_pool:
        db_pool.putconn(conn)


# API Endpoints
@app.get("/api/vessels", response_model=VesselsResponse)
async def get_vessels(
    bbox: str = Query(..., description="Bounding box: minLon,minLat,maxLon,maxLat"),
    zoom: int = Query(..., ge=1, le=20, description="Map zoom level"),
    last_update_time: Optional[str] = Query(
        None, alias="lastUpdateTime", description="ISO 8601 timestamp for delta updates"
    ),
):
    """
    Get vessels in viewport with optional delta support.

    Args:
        bbox: Bounding box as "minLon,minLat,maxLon,maxLat"
        zoom: Map zoom level (used for geohash precision)
        last_update_time: Optional timestamp for delta updates

    Returns:
        VesselsResponse with vessels in viewport
    """
    try:
        bbox_parts = bbox.split(",")
        if len(bbox_parts) != 4:
            raise ValueError("Invalid bbox format")

        min_lon, min_lat, max_lon, max_lat = map(float, bbox_parts)

        # Validate coordinates
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError(
                "Invalid bounding box: min values must be less than max values"
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid bbox parameter: {e}")

    delta_time = None
    is_delta = False
    if last_update_time:
        try:
            delta_time = datetime.fromisoformat(last_update_time.replace("Z", "+00:00"))
            is_delta = True
        except Exception as e:
            logger.warning(f"Invalid lastUpdateTime: {e}")
            # Ignore invalid timestamp, return full dataset

    conn = get_db_connection()

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT 
                mmsi,
                latitude,
                longitude,
                course,
                speed,
                ship_type,
                last_updated
            FROM vessels
            WHERE 
                latitude BETWEEN %s AND %s
                AND longitude BETWEEN %s AND %s
                AND last_updated > NOW() - INTERVAL '2 minutes'
        """

        params = [min_lat, max_lat, min_lon, max_lon]

        # Add delta filter if requested
        if delta_time:
            query += " AND last_updated > %s"
            params.append(delta_time)

        query += " ORDER BY last_updated DESC"

        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()

        cursor.close()

        print(f"DB Rows: {len(rows)}", flush=True)

        # Convert to Vessel models
        vessels = []
        for row in rows:
            vessels.append(
                Vessel(
                    mmsi=row["mmsi"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    course=row["course"],
                    speed=row["speed"],
                    ship_type=row["ship_type"],
                    last_updated=(
                        row["last_updated"].isoformat() if row["last_updated"] else None
                    ),
                )
            )

        # Server time for next delta query
        server_time = datetime.utcnow().isoformat() + "Z"

        logger.info(
            f"Returned {len(vessels)} vessels (delta={is_delta}) at {server_time}"
        )

        return VesselsResponse(
            vessels=vessels,
            server_time=server_time,
            count=len(vessels),
            is_delta=is_delta,
        )

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    finally:
        return_db_connection(conn)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthResponse with system status
    """
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        # Check database connection
        cursor.execute("SELECT 1")
        cursor.fetchone()

        # Get vessel count
        cursor.execute("SELECT COUNT(*) FROM vessels")
        vessel_count = cursor.fetchone()[0]

        cursor.close()

        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat() + "Z",
            database="connected",
            vessels_count=vessel_count,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "database": f"error: {e}",
                "vessels_count": None,
            },
        )

    finally:
        return_db_connection(conn)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "AIS Vessel Tracker API",
        "version": "1.0.0",
        "endpoints": {
            "vessels": "/api/vessels?bbox=minLon,minLat,maxLon,maxLat&zoom=12&lastUpdateTime=ISO8601",
            "health": "/health",
            "docs": "/docs",
        },
    }


# Main entry point
if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 30)
    logger.info("AIS API SERVICE STARTING")
    logger.info("=" * 30)
    logger.info(f"Host: {settings.api_host}")
    logger.info(f"Port: {settings.api_port}")

    uvicorn.run(
        "api_service:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
