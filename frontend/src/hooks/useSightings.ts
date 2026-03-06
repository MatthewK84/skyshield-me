/**
 * SkyShield ME — Data Hooks
 *
 * React Query hooks for fetching sighting and heatmap data
 * with automatic polling intervals.
 */

import { useQuery } from "@tanstack/react-query";
import type { Sighting, HeatmapResponse } from "../types";
import { fetchLiveSightings, fetchHeatmapData } from "../lib/api";

const LIVE_POLL_INTERVAL_MS = 10_000;
const HEATMAP_POLL_INTERVAL_MS = 60_000;

export function useLiveSightings(source?: string) {
  return useQuery<Sighting[], Error>({
    queryKey: ["sightings", "live", source],
    queryFn: (): Promise<Sighting[]> => fetchLiveSightings(source),
    refetchInterval: LIVE_POLL_INTERVAL_MS,
    staleTime: 5_000,
  });
}

export function useHeatmapData(hours: number = 24) {
  return useQuery<HeatmapResponse, Error>({
    queryKey: ["sightings", "heatmap", hours],
    queryFn: (): Promise<HeatmapResponse> => fetchHeatmapData(hours),
    refetchInterval: HEATMAP_POLL_INTERVAL_MS,
    staleTime: 30_000,
  });
}
