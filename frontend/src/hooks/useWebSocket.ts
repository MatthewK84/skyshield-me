/**
 * SkyShield ME — WebSocket Hook
 *
 * Custom hook for real-time live feed with automatic reconnection,
 * heartbeat tracking, and typed message handling.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Sighting, WebSocketMessage } from "../types";

interface UseWebSocketReturn {
  liveSightings: Sighting[];
  isConnected: boolean;
  lastHeartbeat: Date | null;
  connectionAttempts: number;
  clearSightings: () => void;
}

// In production, VITE_WS_URL points to the backend's WebSocket endpoint.
// In development, Vite proxy handles /ws routing.
function getWsUrl(): string {
  const envUrl: string | undefined = import.meta.env.VITE_WS_URL as string | undefined;
  if (envUrl) {
    return `${envUrl}/ws/live-feed`;
  }
  const protocol: string = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/live-feed`;
}

const MAX_RECONNECT_DELAY_MS = 30000;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_LIVE_BUFFER = 200;

export function useWebSocket(): UseWebSocketReturn {
  const [liveSightings, setLiveSightings] = useState<Sighting[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [lastHeartbeat, setLastHeartbeat] = useState<Date | null>(null);
  const [connectionAttempts, setConnectionAttempts] = useState<number>(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearSightings = useCallback((): void => {
    setLiveSightings([]);
  }, []);

  const connect = useCallback((): void => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = new WebSocket(getWsUrl());

    ws.onopen = (): void => {
      setIsConnected(true);
      setConnectionAttempts(0);
    };

    ws.onmessage = (event: MessageEvent<string>): void => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);

        if (message.event === "new_sighting" && message.data !== null) {
          setLiveSightings((prev: Sighting[]): Sighting[] => {
            const updated: Sighting[] = [message.data as Sighting, ...prev];
            return updated.slice(0, MAX_LIVE_BUFFER);
          });
        }

        if (message.event === "heartbeat") {
          setLastHeartbeat(new Date());
        }
      } catch (parseError: unknown) {
        console.error("WebSocket message parse error:", parseError);
      }
    };

    ws.onclose = (): void => {
      setIsConnected(false);
      wsRef.current = null;

      // Exponential backoff reconnection
      setConnectionAttempts((prev: number): number => {
        const next: number = prev + 1;
        const delay: number = Math.min(
          BASE_RECONNECT_DELAY_MS * Math.pow(2, next),
          MAX_RECONNECT_DELAY_MS
        );

        reconnectTimeoutRef.current = setTimeout((): void => {
          connect();
        }, delay);

        return next;
      });
    };

    ws.onerror = (): void => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  useEffect((): (() => void) => {
    connect();

    return (): void => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return {
    liveSightings,
    isConnected,
    lastHeartbeat,
    connectionAttempts,
    clearSightings,
  };
}
