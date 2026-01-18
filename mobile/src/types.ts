/**
 * Vessel data types.
 */

export interface Vessel {
  mmsi: number;
  latitude: number;
  longitude: number;
  course: number | null;
  speed: number | null;
  ship_type: number | null;
  last_updated: string; // ISO 8601 timestamp
}

export interface VesselsResponse {
  vessels: Vessel[];
  server_time: string; // ISO 8601 timestamp
  count: number;
  is_delta: boolean;
}

export interface Bbox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

