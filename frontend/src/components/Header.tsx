/**
 * SkyShield ME — Header Component
 *
 * Top navigation bar with branding, system status indicators,
 * and the current UTC timestamp.
 */

import { useEffect, useState } from "react";
import { Shield, Clock, Database, Cpu } from "lucide-react";

interface HeaderProps {
  isConnected: boolean;
  sightingCount: number;
}

export default function Header({
  isConnected,
  sightingCount,
}: HeaderProps): JSX.Element {
  const [utcTime, setUtcTime] = useState<string>("");

  useEffect((): (() => void) => {
    const updateClock = (): void => {
      const now: Date = new Date();
      const formatted: string = now.toISOString().replace("T", " ").slice(0, 19) + "Z";
      setUtcTime(formatted);
    };

    updateClock();
    const interval: ReturnType<typeof setInterval> = setInterval(updateClock, 1000);

    return (): void => clearInterval(interval);
  }, []);

  return (
    <header className="h-12 bg-sky-panel border-b border-sky-border flex items-center justify-between px-4">
      {/* ── Branding ─────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Shield size={22} className="text-sky-accent" />
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-emerald-400 rounded-full animate-pulse-slow" />
          </div>
          <h1 className="font-display font-extrabold text-base tracking-tight">
            <span className="text-sky-accent">SKY</span>
            <span className="text-white">SHIELD</span>
            <span className="text-sky-muted ml-1 font-medium text-sm">ME</span>
          </h1>
        </div>

        <div className="h-4 w-px bg-sky-border mx-1" />

        <span className="text-[10px] font-mono text-sky-muted uppercase tracking-widest">
          Regional Detection Dashboard
        </span>
      </div>

      {/* ── Status Indicators ────────────────────────────── */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-xs font-mono text-sky-muted">
          <Database size={11} />
          <span>{sightingCount} contacts</span>
        </div>

        <div className="flex items-center gap-1.5 text-xs font-mono text-sky-muted">
          <Cpu size={11} />
          <span
            className={
              isConnected ? "text-emerald-400" : "text-amber-400"
            }
          >
            {isConnected ? "CONNECTED" : "OFFLINE"}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-xs font-mono text-sky-accent">
          <Clock size={11} />
          <span>{utcTime}</span>
        </div>
      </div>
    </header>
  );
}
