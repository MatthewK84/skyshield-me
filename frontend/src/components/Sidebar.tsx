/**
 * SkyShield ME — Sidebar Component
 *
 * Contains:
 * - Connection status indicator
 * - Layer filter toggles (ADS-B / Social)
 * - Confidence threshold slider
 * - Live Intel Feed — scrolling list of raw social media text
 * - Sighting statistics
 */

import { useMemo } from "react";
import {
  Radio,
  RadioTower,
  Wifi,
  WifiOff,
  Filter,
  AlertTriangle,
  Plane,
  Eye,
  Activity,
  ChevronRight,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { Sighting, FilterState } from "../types";

// ─── Stat Card ──────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: number;
  icon: JSX.Element;
  color: string;
}

function StatCard({ label, value, icon, color }: StatCardProps): JSX.Element {
  return (
    <div className="bg-sky-dark/50 rounded-lg p-3 border border-sky-border/50">
      <div className="flex items-center gap-2 mb-1">
        <div style={{ color }}>{icon}</div>
        <span className="text-sky-muted text-xs font-mono uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div className="text-2xl font-display font-bold" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

// ─── Intel Feed Item ────────────────────────────────────────────

interface FeedItemProps {
  sighting: Sighting;
  onClick: (s: Sighting) => void;
}

function IntelFeedItem({ sighting, onClick }: FeedItemProps): JSX.Element {
  const isAdsb: boolean = sighting.source === "ADSB";
  const timeAgo: string = formatDistanceToNow(new Date(sighting.timestamp), {
    addSuffix: true,
  });
  const borderColor: string = isAdsb ? "#3b82f6" : "#ef4444";

  const displayText: string = isAdsb
    ? `ADS-B: ${sighting.callsign ?? sighting.icao_hex ?? "Unknown"} — ${sighting.altitude?.toFixed(0) ?? "?"} ft`
    : sighting.raw_text?.slice(0, 120) ?? "Social inference alert";

  return (
    <button
      onClick={(): void => onClick(sighting)}
      className="w-full text-left p-3 rounded-lg border transition-all duration-200 hover:bg-white/5 hover:border-white/20 group"
      style={{ borderColor: `${borderColor}30`, borderWidth: "1px" }}
    >
      <div className="flex items-start gap-2">
        <div
          className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
          style={{ background: borderColor, boxShadow: `0 0 8px ${borderColor}80` }}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-[10px] font-mono font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
              style={{ background: `${borderColor}20`, color: borderColor }}
            >
              {isAdsb ? "ADS-B" : "SOCIAL"}
            </span>
            <span className="text-sky-muted text-[10px] font-mono">{timeAgo}</span>
          </div>
          <p className="text-sm text-gray-300 leading-snug line-clamp-2 font-body">
            {displayText}
          </p>
          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-sky-muted font-mono">
            <span>
              {sighting.lat.toFixed(2)}, {sighting.lon.toFixed(2)}
            </span>
            <span>CONF: {sighting.confidence_score}%</span>
          </div>
        </div>
        <ChevronRight
          size={14}
          className="text-sky-muted group-hover:text-white transition-colors mt-1"
        />
      </div>
    </button>
  );
}

// ─── Main Sidebar ───────────────────────────────────────────────

interface SidebarProps {
  sightings: Sighting[];
  liveSightings: Sighting[];
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  onSightingClick: (s: Sighting) => void;
  isConnected: boolean;
}

export default function Sidebar({
  sightings,
  liveSightings,
  filters,
  onFiltersChange,
  onSightingClick,
  isConnected,
}: SidebarProps): JSX.Element {
  const allSightings: Sighting[] = useMemo((): Sighting[] => {
    const map = new Map<string, Sighting>();
    for (const s of [...liveSightings, ...sightings]) {
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
  }, [sightings, liveSightings]);

  const adsbCount: number = allSightings.filter((s) => s.source === "ADSB").length;
  const socialCount: number = allSightings.filter(
    (s) => s.source === "SOCIAL_INFERENCE"
  ).length;

  const feedItems: Sighting[] = allSightings.slice(0, 50);

  return (
    <aside className="w-[380px] h-full flex flex-col bg-sky-panel border-r border-sky-border overflow-hidden">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="p-4 border-b border-sky-border">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display font-bold text-lg tracking-tight">
            Live Intel Feed
          </h2>
          <div className="flex items-center gap-2">
            {isConnected ? (
              <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-mono">
                <Wifi size={12} />
                <span>LIVE</span>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-slow" />
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-amber-400 text-xs font-mono">
                <WifiOff size={12} />
                <span>RECONNECTING</span>
              </div>
            )}
          </div>
        </div>

        {/* ── Stats ──────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <StatCard
            label="Total"
            value={allSightings.length}
            icon={<Eye size={14} />}
            color="#06b6d4"
          />
          <StatCard
            label="ADS-B"
            value={adsbCount}
            icon={<Plane size={14} />}
            color="#3b82f6"
          />
          <StatCard
            label="Social"
            value={socialCount}
            icon={<AlertTriangle size={14} />}
            color="#ef4444"
          />
        </div>
      </div>

      {/* ── Filters ────────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-sky-border">
        <div className="flex items-center gap-2 mb-2">
          <Filter size={12} className="text-sky-muted" />
          <span className="text-xs font-mono text-sky-muted uppercase tracking-wider">
            Layer Filters
          </span>
        </div>

        <div className="flex gap-2 mb-3">
          <button
            onClick={(): void =>
              onFiltersChange({ ...filters, showAdsb: !filters.showAdsb })
            }
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
              filters.showAdsb
                ? "bg-sky-adsb/20 text-sky-adsb border border-sky-adsb/40"
                : "bg-sky-dark/50 text-sky-muted border border-sky-border"
            }`}
          >
            <Plane size={12} />
            ADS-B
          </button>

          <button
            onClick={(): void =>
              onFiltersChange({ ...filters, showSocial: !filters.showSocial })
            }
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
              filters.showSocial
                ? "bg-sky-social/20 text-sky-social border border-sky-social/40"
                : "bg-sky-dark/50 text-sky-muted border border-sky-border"
            }`}
          >
            <RadioTower size={12} />
            Social
          </button>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono text-sky-muted uppercase tracking-wider">
              Min Confidence
            </span>
            <span className="text-xs font-mono text-sky-accent">
              {filters.minConfidence}%
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={filters.minConfidence}
            onChange={(e): void =>
              onFiltersChange({
                ...filters,
                minConfidence: parseInt(e.target.value, 10),
              })
            }
            className="w-full h-1 bg-sky-border rounded-lg appearance-none cursor-pointer accent-sky-accent"
          />
        </div>
      </div>

      {/* ── Feed List ──────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 scrollbar-thin">
        {feedItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-sky-muted">
            <Activity size={32} className="mb-2 opacity-50" />
            <p className="text-sm font-body">Awaiting intel...</p>
            <p className="text-xs font-mono mt-1">No sightings in the live window</p>
          </div>
        ) : (
          feedItems.map(
            (sighting: Sighting): JSX.Element => (
              <IntelFeedItem
                key={sighting.id}
                sighting={sighting}
                onClick={onSightingClick}
              />
            )
          )
        )}
      </div>
    </aside>
  );
}
