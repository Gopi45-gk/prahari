/**
 * PRAHARI Unified API Hooks
 * 
 * Shared React hooks for WebSocket streams and REST polling.
 * All routes consume the Unified Gateway on port 8001.
 */

import { useEffect, useRef, useState, useCallback } from "react";

// ── Gateway Base URL ─────────────────────────────────────────────────────
export const API_BASE = "http://localhost:8001";
export const WS_BASE = "ws://localhost:8001";

// ═══════════════════════════════════════════════════════════════════════════
// REST Polling Hook
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Polls a REST endpoint at a given interval and returns the latest data.
 * 
 * @param path  — API path (e.g. "/api/dashboard-summary")
 * @param intervalMs — polling interval in ms (default 5000)
 */
export function usePrahariQuery<T>(path: string, intervalMs = 5000): {
  data: T | null;
  loading: boolean;
  error: string | null;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json);
          setLoading(false);
          setError(null);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message ?? "Fetch failed");
          setLoading(false);
        }
      }
    };

    // Initial fetch
    fetchData();

    // Polling interval
    const id = setInterval(fetchData, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [path, intervalMs]);

  return { data, loading, error };
}

// ═══════════════════════════════════════════════════════════════════════════
// WebSocket Hook (server-push, no client frames)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Connects to a WebSocket endpoint that pushes data server-side.
 * Auto-reconnects on disconnect.
 * 
 * @param path — WS path (e.g. "/ws/infrastructure")
 * @param onMessage — callback receiving parsed JSON messages
 */
export function usePrahariWebSocket<T = any>(
  path: string,
  onMessage: (data: T) => void,
): { connected: boolean } {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let unmounted = false;

    const connect = () => {
      if (unmounted) return;
      ws = new WebSocket(`${WS_BASE}${path}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!unmounted) setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as T;
          onMessageRef.current(data);
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        if (!unmounted) {
          setConnected(false);
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    };
  }, [path]);

  return { connected };
}
