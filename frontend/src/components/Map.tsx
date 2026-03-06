/**
 * SkyShield ME — Map Component
 *
 * Leaflet map centered on the Middle East AOR with two distinct layers:
 * - Blue plane icons for confirmed ADS-B traffic
 * - Red pulsating circles for social-inference threats
 *
 * Uses react-leaflet for declarative map rendering.
 */

import { useEffect, useRef, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  CircleMarker,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { Sighting, FilterState } from "../types";
import { formatDistanceToNow } from "date-fns";

// ─── Custom Icons ───────────────────────────────────────────────

const ADSB_ICON: L.DivIcon = L.divIcon({
  className: "adsb-marker",
  html: `<div style="
    width: 28px; height: 28px;
    background: #3b82f6;
    border: 2px solid #93c5fd;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.6);
  ">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5">
      <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.4-.1.9.3 1.1l5.5 3.2-2.2 2.2-2.5-.5c-.3-.1-.6 0-.8.2l-.2.3c-.2.3-.1.7.1.9l2.8 2.1 2.1 2.8c.2.3.6.3.9.1l.3-.2c.2-.2.3-.5.2-.8l-.5-2.5 2.2-2.2 3.2 5.5c.2.4.7.5 1.1.3l.5-.3c.4-.2.6-.6.5-1.1z"/>
    </svg>
  </div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  popupAnchor: [0, -16],
});

const SOCIAL_ICON: L.DivIcon = L.divIcon({
  className: "social-marker",
  html: `<div style="position: relative; width: 32px; height: 32px;">
    <div style="
      position: absolute; inset: 0;
      background: rgba(239, 68, 68, 0.3);
      border-radius: 50%;
      animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;
    "></div>
    <div style="
      position: absolute; inset: 4px;
      background: #ef4444;
      border: 2px solid #fca5a5;
      border-radius: 50%;
      box-shadow: 0 0 16px rgba(239, 68, 68, 0.7);
    "></div>
  </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  popupAnchor: [0, -18],
});

// ─── Middle East Center ─────────────────────────────────────────
const ME_CENTER: [number, number] = [30.0, 47.0];
const ME_ZOOM = 5;

// ─── Auto-fit bounds to sightings ───────────────────────────────

interface AutoFitProps {
  sightings: Sighting[];
}

function AutoFitBounds({ sightings }: AutoFitProps): null {
  const map = useMap();
  const hasFitted = useRef<boolean>(false);

  useEffect((): void => {
    if (sightings.length > 0 && !hasFitted.current) {
      const bounds: L.LatLngBoundsExpression = sightings.map(
        (s: Sighting): [number, number] => [s.lat, s.lon]
      );
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 8 });
      hasFitted.current = true;
    }
  }, [map, sightings]);

  return null;
}

// ─── Popup Content ──────────────────────────────────────────────

interface PopupContentProps {
  sighting: Sighting;
}

function SightingPopup({ sighting }: PopupContentProps): JSX.Element {
  const isAdsb: boolean = sighting.source === "ADSB";
  const timeAgo: string = formatDistanceToNow(new Date(sighting.timestamp), {
    addSuffix: true,
  });

  return (
    <div className="font-body text-sm" style={{ minWidth: "220px", color: "#1e293b" }}>
      <div
        className="font-display font-bold text-base mb-2 pb-1"
        style={{ borderBottom: "2px solid", borderColor: isAdsb ? "#3b82f6" : "#ef4444" }}
      >
        {isAdsb ? "ADS-B Contact" : "Social Intel"}
      </div>

      <div className="space-y-1">
        {sighting.callsign && (
          <div>
            <span className="font-semibold">Callsign:</span> {sighting.callsign}
          </div>
        )}
        {sighting.icao_hex && (
          <div>
            <span className="font-semibold">ICAO:</span> {sighting.icao_hex}
          </div>
        )}
        {sighting.altitude !== null && (
          <div>
            <span className="font-semibold">Alt:</span> {sighting.altitude.toFixed(0)} ft
          </div>
        )}
        {sighting.speed_kts !== null && (
          <div>
            <span className="font-semibold">Speed:</span> {sighting.speed_kts.toFixed(0)} kts
          </div>
        )}
        <div>
          <span className="font-semibold">Confidence:</span> {sighting.confidence_score}%
        </div>
        <div>
          <span className="font-semibold">Position:</span>{" "}
          {sighting.lat.toFixed(4)}, {sighting.lon.toFixed(4)}
        </div>
        <div className="text-xs text-gray-500 mt-1">{timeAgo}</div>
      </div>

      {sighting.raw_text && (
        <div
          className="mt-2 p-2 rounded text-xs italic"
          style={{ background: "#f1f5f9", maxHeight: "80px", overflow: "auto" }}
        >
          &ldquo;{sighting.raw_text.slice(0, 200)}
          {sighting.raw_text.length > 200 ? "..." : ""}&rdquo;
        </div>
      )}
    </div>
  );
}

// ─── Main Map Component ─────────────────────────────────────────

interface MapProps {
  sightings: Sighting[];
  filters: FilterState;
  onSightingClick: (sighting: Sighting) => void;
}

export default function SkyShieldMap({
  sightings,
  filters,
  onSightingClick,
}: MapProps): JSX.Element {
  const filteredSightings: Sighting[] = useMemo((): Sighting[] => {
    return sightings.filter((s: Sighting): boolean => {
      const sourceOk: boolean =
        (s.source === "ADSB" && filters.showAdsb) ||
        (s.source === "SOCIAL_INFERENCE" && filters.showSocial);
      const confOk: boolean = s.confidence_score >= filters.minConfidence;
      return sourceOk && confOk;
    });
  }, [sightings, filters]);

  const adsbSightings: Sighting[] = useMemo(
    (): Sighting[] => filteredSightings.filter((s) => s.source === "ADSB"),
    [filteredSightings]
  );

  const socialSightings: Sighting[] = useMemo(
    (): Sighting[] => filteredSightings.filter((s) => s.source === "SOCIAL_INFERENCE"),
    [filteredSightings]
  );

  return (
    <MapContainer
      center={ME_CENTER}
      zoom={ME_ZOOM}
      className="w-full h-full"
      zoomControl={false}
      style={{ background: "#0a0e1a" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://carto.com">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />

      <AutoFitBounds sightings={filteredSightings} />

      {/* ── ADS-B Layer (Blue planes) ────────────────────── */}
      {adsbSightings.map(
        (sighting: Sighting): JSX.Element => (
          <Marker
            key={sighting.id}
            position={[sighting.lat, sighting.lon]}
            icon={ADSB_ICON}
            eventHandlers={{
              click: (): void => onSightingClick(sighting),
            }}
          >
            <Popup>
              <SightingPopup sighting={sighting} />
            </Popup>
          </Marker>
        )
      )}

      {/* ── Social Inference Layer (Red pulsating) ───────── */}
      {socialSightings.map(
        (sighting: Sighting): JSX.Element => (
          <Marker
            key={sighting.id}
            position={[sighting.lat, sighting.lon]}
            icon={SOCIAL_ICON}
            eventHandlers={{
              click: (): void => onSightingClick(sighting),
            }}
          >
            <Popup>
              <SightingPopup sighting={sighting} />
            </Popup>
          </Marker>
        )
      )}

      {/* ── Heatmap-style circles for density overlay ────── */}
      {filteredSightings.map(
        (s: Sighting): JSX.Element => (
          <CircleMarker
            key={`heat-${s.id}`}
            center={[s.lat, s.lon]}
            radius={s.confidence_score / 8}
            pathOptions={{
              color: s.source === "ADSB" ? "#3b82f6" : "#ef4444",
              fillColor: s.source === "ADSB" ? "#3b82f6" : "#ef4444",
              fillOpacity: 0.15,
              weight: 0,
            }}
          />
        )
      )}
    </MapContainer>
  );
}
