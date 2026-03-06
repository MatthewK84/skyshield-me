/**
 * SkyShield ME — API Client
 *
 * Typed fetch wrappers for the FastAPI backend.
 */

import type { Sighting, HeatmapResponse, HealthStatus } from "../types";

// In production (Railway), VITE_API_URL points to the backend's public URL.
// In development, Vite proxy handles /api routing to localhost:8000.
const API_BASE: string = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : "/api/v1";

async function fetchJSON<T>(url: string): Promise<T> {
  const response: Response = await fetch(url);

  if (!response.ok) {
    const errorText: string = await response.text();
    throw new Error(`API Error ${response.status}: ${errorText}`);
  }

  const data: T = await response.json();
  return data;
}

export async function fetchLiveSightings(
  source?: string,
  limit: number = 200
): Promise<Sighting[]> {
  const params = new URLSearchParams();
  if (source) params.set("source", source);
  params.set("limit", limit.toString());

  const url = `${API_BASE}/sightings/live?${params.toString()}`;
  return fetchJSON<Sighting[]>(url);
}

export async function fetchHeatmapData(
  hours: number = 24,
  precision: number = 2
): Promise<HeatmapResponse> {
  const params = new URLSearchParams({
    hours: hours.toString(),
    precision: precision.toString(),
  });

  const url = `${API_BASE}/sightings/heatmap?${params.toString()}`;
  return fetchJSON<HeatmapResponse>(url);
}

export async function fetchHealth(): Promise<HealthStatus> {
  const healthBase: string = import.meta.env.VITE_API_URL ?? "";
  return fetchJSON<HealthStatus>(`${healthBase}/health`);
}
