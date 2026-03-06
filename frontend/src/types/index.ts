/**
 * SkyShield ME — Type Definitions
 *
 * All interfaces strictly typed. No use of `any`.
 */

export type SightingSource = "ADSB" | "SOCIAL_INFERENCE";

export interface Sighting {
  id: string;
  lat: number;
  lon: number;
  altitude: number | null;
  speed_kts: number | null;
  heading: number | null;
  source: SightingSource;
  confidence_score: number;
  callsign: string | null;
  icao_hex: string | null;
  raw_text: string | null;
  metadata_json: Record<string, string> | null;
  timestamp: string;
  created_at: string;
}

export interface HeatmapPoint {
  lat: number;
  lon: number;
  intensity: number;
  count: number;
}

export interface HeatmapResponse {
  points: HeatmapPoint[];
  total_sightings: number;
  time_range_hours: number;
}

export interface WebSocketMessage {
  event: "new_sighting" | "heartbeat" | "error";
  data: Sighting | null;
  message: string | null;
  timestamp: string;
}

export interface HealthStatus {
  status: "healthy" | "degraded";
  version: string;
  db_connected: boolean;
  redis_connected: boolean;
}

export interface MapViewState {
  center: [number, number];
  zoom: number;
}

export interface FilterState {
  showAdsb: boolean;
  showSocial: boolean;
  minConfidence: number;
}
