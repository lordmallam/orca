"""
AIS Ingest Service

Connects to aisstream.io WebSocket, processes PositionReport messages,
and stores vessel positions in PostgreSQL using batch UPSERT.

Features:
- WebSocket client with auto-reconnect
- Batch UPSERT to PostgreSQL
- Geohash calculation for spatial indexing
- Error handling and logging
"""

import asyncio
import websockets
import json
import queue
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
import pygeohash as pgh
from dateutil import parser as date_parser
from config import settings


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AISIngestService:
    """
    Main ingest service that connects to aisstream.io and stores data.
    """

    def __init__(self):
        self.api_key = settings.aisstream_api_key
        self.ws_url = settings.aisstream_url
        self.batch_size = settings.batch_size
        self.batch_interval = settings.batch_interval_seconds
        self.message_queue = queue.Queue()
        self.db_conn = None
        self.db_cursor = None

        self.stats = {
            "messages_received": 0,
            "position_reports": 0,
            "vessels_upserted": 0,
            "batches_processed": 0,
            "errors": 0,
            "start_time": time.time(),
        }

        self.running = False

    def connect_database(self):
        """Establish database connection."""
        try:
            database_url = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
            self.db_conn = psycopg2.connect(database_url)
            self.db_cursor = self.db_conn.cursor()
            logger.info("Connected to database")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def close_database(self):
        """Close database connection."""
        if self.db_cursor:
            self.db_cursor.close()
        if self.db_conn:
            self.db_conn.close()
        logger.info("Database connection closed")

    async def connect_websocket(self):
        """
        Connect to aisstream.io WebSocket and receive messages.
        Includes auto-reconnect logic.
        """
        retry_delay = 5

        while self.running:
            try:
                logger.info(f"Connecting to {self.ws_url}...")

                async with websockets.connect(self.ws_url) as websocket:
                    subscribe_message = {
                        "APIKey": self.api_key,
                        "BoundingBoxes": [[[-180, -90], [180, 90]]],
                        "FilterMessageTypes": ["PositionReport"],
                    }

                    await websocket.send(json.dumps(subscribe_message))
                    logger.info("Subscribed to PositionReport messages")

                    retry_delay = 5

                    while self.running:
                        try:
                            message_raw = await websocket.recv()
                            self.stats["messages_received"] += 1
                            self.message_queue.put(message_raw)
                            # Log progress every 1000 messages
                            if self.stats["messages_received"] % 1000 == 0:
                                self.log_stats()

                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("WebSocket connection closed")
                            break

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.stats["errors"] += 1

                if self.running:
                    logger.info(f"Reconnecting in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)

    def process_message_queue(self):
        """
        Process messages from queue and batch UPSERT to database.
        Uses dictionary for automatic deduplication by MMSI.
        Runs in a separate thread.
        """
        batch = {}
        last_batch_time = time.time()

        logger.info("Message processor started")

        while self.running or not self.message_queue.empty():
            try:
                # Get message from queue (with timeout)
                try:
                    message_raw = self.message_queue.get(timeout=0.1)
                except queue.Empty:
                    # Check if we should flush based on time
                    if batch and (time.time() - last_batch_time >= self.batch_interval):
                        self.batch_upsert(list(batch.values()))
                        batch = {}
                        last_batch_time = time.time()
                    continue

                # Parse message
                try:
                    message = json.loads(message_raw)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse message")
                    self.stats["errors"] += 1
                    continue

                # Process only PositionReport messages
                if message.get("MessageType") == "PositionReport":
                    self.stats["position_reports"] += 1
                    vessel_data = self.extract_vessel_data(message)

                    if vessel_data:
                        mmsi = vessel_data["mmsi"]
                        if (
                            mmsi not in batch
                            or vessel_data["last_updated"] > batch[mmsi]["last_updated"]
                        ):
                            batch[mmsi] = vessel_data

                if len(batch) >= self.batch_size or (
                    batch and (time.time() - last_batch_time >= self.batch_interval)
                ):
                    self.batch_upsert(list(batch.values()))
                    batch = {}
                    last_batch_time = time.time()

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                self.stats["errors"] += 1

        # Flush remaining batch
        if batch:
            self.batch_upsert(list(batch.values()))

        logger.info("Message processor stopped")

    def extract_vessel_data(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract and validate vessel data from PositionReport message.

        Returns:
            Dictionary with vessel data, or None if invalid
        """
        try:
            metadata = message.get("MetaData", {})
            position_report = message.get("Message", {}).get("PositionReport", {})

            mmsi = metadata.get("MMSI")
            latitude = position_report.get("Latitude")
            longitude = position_report.get("Longitude")
            course = position_report.get("Cog")
            speed = position_report.get("Sog")
            ship_type = metadata.get("ShipType")
            timestamp = metadata.get("time_utc")

            # Validation
            if not mmsi or mmsi <= 0:
                return None
            if latitude is None or not (-90 <= latitude <= 90):
                return None
            if longitude is None or not (-180 <= longitude <= 180):
                return None
            if course is not None and not (0 <= course < 360):
                course = None
            if speed is not None and speed < 0:
                speed = None

            geohash = pgh.encode(latitude, longitude, precision=7)
            geohash_5 = geohash[:5]

            parsed_timestamp = None
            if timestamp:
                try:
                    timestamp_clean = timestamp.replace(" UTC", "")
                    parsed_timestamp = date_parser.parse(timestamp_clean)
                except Exception as e:
                    logger.warning(f"Failed to parse timestamp '{timestamp}': {e}")
                    parsed_timestamp = datetime.utcnow()
            else:
                parsed_timestamp = datetime.utcnow()

            processed_data = {
                "mmsi": mmsi,
                "latitude": latitude,
                "longitude": longitude,
                "course": course,
                "speed": speed,
                "ship_type": ship_type,
                "geohash": geohash,
                "geohash_5": geohash_5,
                "last_updated": parsed_timestamp,
            }

            return processed_data

        except Exception as e:
            logger.warning(f"Failed to extract vessel data: {e}")
            return None

    def batch_upsert(self, batch: list):
        """
        Batch UPSERT vessels to database using INSERT ... ON CONFLICT UPDATE.

        Args:
            batch: List of vessel data dictionaries
        """
        if not batch:
            return

        start_time = time.time()

        try:
            # Prepare data for execute_values
            values = [
                (
                    vessel["mmsi"],
                    vessel["latitude"],
                    vessel["longitude"],
                    f"POINT({vessel['longitude']} {vessel['latitude']})",
                    vessel["course"],
                    vessel["speed"],
                    vessel["ship_type"],
                    vessel["geohash"],
                    vessel["geohash_5"],
                    vessel["last_updated"],
                )
                for vessel in batch
            ]

            # UPSERT query
            query = """
                INSERT INTO vessels (
                    mmsi, latitude, longitude, location, course, speed,
                    ship_type, geohash, geohash_5, last_updated
                )
                VALUES %s
                ON CONFLICT (mmsi) 
                DO UPDATE SET
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    location = EXCLUDED.location,
                    course = EXCLUDED.course,
                    speed = EXCLUDED.speed,
                    ship_type = EXCLUDED.ship_type,
                    geohash = EXCLUDED.geohash,
                    geohash_5 = EXCLUDED.geohash_5,
                    last_updated = EXCLUDED.last_updated,
                    received_at = NOW()
            """

            execute_values(
                self.db_cursor,
                query,
                values,
                template="(%s, %s, %s, ST_GeogFromText(%s), %s, %s, %s, %s, %s, %s)",
            )

            self.db_conn.commit()

            duration_ms = int((time.time() - start_time) * 1000)
            self.stats["vessels_upserted"] += len(batch)
            self.stats["batches_processed"] += 1

            logger.debug(f"Batch upserted: {len(batch)} vessels in {duration_ms}ms")

        except Exception as e:
            logger.error(f"Batch UPSERT failed: {e}")
            self.db_conn.rollback()
            self.stats["errors"] += 1

    def log_stats(self):
        """Log current statistics."""
        elapsed = time.time() - self.stats["start_time"]
        msg_rate = self.stats["messages_received"] / elapsed if elapsed > 0 else 0
        pos_rate = self.stats["position_reports"] / elapsed if elapsed > 0 else 0
        queue_size = self.message_queue.qsize()

        logger.info(
            f"Stats: {self.stats['messages_received']:,} msgs "
            f"({msg_rate:.1f}/s) | "
            f"{self.stats['position_reports']:,} positions "
            f"({pos_rate:.1f}/s) | "
            f"{self.stats['vessels_upserted']:,} vessels upserted | "
            f"Queue: {queue_size:,} | "
            f"Errors: {self.stats['errors']}"
        )

    def cleanup_stale_vessels(self):
        """
        Periodically delete stale vessels (older than 2 minutes).
        Runs in a separate thread.
        """
        logger.info("Stale vessel cleanup started")

        while self.running:
            try:
                time.sleep(60)  # Run every minute

                if not self.running:
                    break

                # Call database function to delete stale vessels
                self.db_cursor.execute("SELECT delete_stale_vessels()")
                deleted_count = self.db_cursor.fetchone()[0]
                self.db_conn.commit()

                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} stale vessels")

            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                self.db_conn.rollback()

        logger.info("Stale vessel cleanup stopped")

    def start(self):
        """Start the ingest service."""
        logger.info("=" * 30)
        logger.info("AIS INGEST SERVICE STARTING")
        logger.info("=" * 30)

        if not self.api_key or self.api_key == "your_api_key_here":
            logger.error("AISSTREAM_API_KEY not configured")
            logger.error("Please set AISSTREAM_API_KEY in .env file")
            return

        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Batch interval: {self.batch_interval}s")

        self.connect_database()
        self.running = True

        processor_thread = threading.Thread(
            target=self.process_message_queue, daemon=True
        )
        processor_thread.start()

        cleanup_thread = threading.Thread(
            target=self.cleanup_stale_vessels, daemon=True
        )
        cleanup_thread.start()

        def log_stats_periodically():
            while self.running:
                time.sleep(30)
                if self.running:
                    self.log_stats()

        stats_thread = threading.Thread(target=log_stats_periodically, daemon=True)
        stats_thread.start()

        logger.info("Starting WebSocket client...")

        try:
            asyncio.run(self.connect_websocket())
        except KeyboardInterrupt:
            logger.info("\n Shutdown requested")
        finally:
            self.stop()

    def stop(self):
        """Stop the ingest service gracefully."""
        logger.info("Stopping ingest service...")
        self.running = False

        logger.info(
            f"Waiting for queue to empty ({self.message_queue.qsize()} messages)..."
        )
        time.sleep(2)
        self.log_stats()

        self.close_database()

        logger.info("=" * 30)
        logger.info("AIS INGEST SERVICE STOPPED")
        logger.info("=" * 30)


def main():
    """Main entry point."""
    service = AISIngestService()
    service.start()


if __name__ == "__main__":
    main()
