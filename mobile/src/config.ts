/**
 * Configuration for the AIS Viewer mobile app.
 */

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const MAPBOX_ACCESS_TOKEN = process.env.EXPO_PUBLIC_MAPBOX_TOKEN || "";
export const POLL_INTERVAL_MS = 10000; // 10 seconds
export const MIN_ZOOM_LEVEL = 4; //
export const VESSELS_MAX_ZOOM_LEVEL = 12; //
export const DEFAULT_MAP_CENTER = {
  longitude: 4.8998, // Amsterdam, Netherlands (highest vessel concentration)
  latitude: 52.3701,
};

export const DEFAULT_MAP_ZOOM = 11; // Zoom in closer to see vessels

// Vessel Configuration
export const STALE_VESSEL_TIMEOUT_MS = 120000; // 2 minutes
