/**
 * SkyShield ME — Application Root
 *
 * Composes the Header, Map, and Sidebar components.
 * Manages global filter state and fuses React Query data
 * with WebSocket live sightings.
 */

import { useState, useMemo, useCallback } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Header from "./components/Header";
import SkyShieldMap from "./components/Map";
import Sidebar from "./components/Sidebar";
import { useLiveSightings } from "./hooks/useSightings";
import { useWebSocket } from "./hooks/useWebSocket";
import type { Sighting, FilterState } from "./types";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      retryDelay: (attemptIndex: number): number =>
        Math.min(1000 * 2 ** attemptIndex, 15000),
    },
  },
});

function Dashboard(): JSX.Element {
  // ── Filter State ──────────────────────────────────────────
  const [filters, setFilters] = useState<FilterState>({
    showAdsb: true,
    showSocial: true,
    minConfidence: 0,
  });

  // ── Data Sources ──────────────────────────────────────────
  const { data: polledSightings } = useLiveSightings();
  const { liveSightings, isConnected } = useWebSocket();

  // ── Fuse polled + WebSocket sightings (deduplicated) ──────
  const allSightings: Sighting[] = useMemo((): Sighting[] => {
    const map = new Map<string, Sighting>();

    const polled: Sighting[] = polledSightings ?? [];
    for (const s of polled) {
      map.set(s.id, s);
    }
    for (const s of liveSightings) {
      if (!map.has(s.id)) {
        map.set(s.id, s);
      }
    }

    const combined: Sighting[] = Array.from(map.values());
    combined.sort(
      (a: Sighting, b: Sighting): number =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
    return combined;
  }, [polledSightings, liveSightings]);

  // ── Handlers ──────────────────────────────────────────────
  const handleFiltersChange = useCallback((newFilters: FilterState): void => {
    setFilters(newFilters);
  }, []);

  const handleSightingClick = useCallback((_sighting: Sighting): void => {
    // Future: pan map to sighting, open detail panel
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-sky-dark">
      <Header isConnected={isConnected} sightingCount={allSightings.length} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          sightings={polledSightings ?? []}
          liveSightings={liveSightings}
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onSightingClick={handleSightingClick}
          isConnected={isConnected}
        />

        <main className="flex-1 relative">
          <SkyShieldMap
            sightings={allSightings}
            filters={filters}
            onSightingClick={handleSightingClick}
          />

          {/* ── Map Legend Overlay ────────────────────────── */}
          <div className="absolute bottom-4 right-4 bg-sky-panel/90 backdrop-blur-sm border border-sky-border rounded-lg p-3 text-xs font-mono space-y-1.5 z-[1000]">
            <div className="text-sky-muted uppercase tracking-widest text-[10px] mb-1 font-bold">
              Legend
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-sky-adsb shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
              <span className="text-gray-300">Confirmed ADS-B</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-sky-social shadow-[0_0_8px_rgba(239,68,68,0.5)]" />
              <span className="text-gray-300">Social Inference</span>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App(): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
}
