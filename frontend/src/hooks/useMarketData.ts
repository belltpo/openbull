import { useEffect, useMemo, useRef, useState } from "react";
import { getWebSocketApiKey, getWebSocketConfig } from "@/api/websocket";
import { notifyBrokerIssue } from "@/lib/brokerIssue";

export type SubscriptionMode = "LTP" | "Quote" | "Depth";
export interface DepthLevel { price?: number; quantity?: number; orders?: number; }
export interface MarketTickData {
  ltp?: number; open?: number; high?: number; low?: number; close?: number;
  volume?: number; oi?: number; bid_price?: number; ask_price?: number;
  bid_size?: number; ask_size?: number;
  depth?: { buy?: DepthLevel[]; sell?: DepthLevel[] };
  change?: number; change_percent?: number;
}
export interface SymbolData {
  symbol: string; exchange: string; data: MarketTickData; lastUpdate: number;
}
export type ConnectionState =
  | "idle" | "connecting" | "connected" | "authenticating"
  | "authenticated" | "error" | "closed";
interface UseMarketDataOptions {
  symbols: Array<{ symbol: string; exchange: string }>;
  mode?: SubscriptionMode;
  enabled?: boolean;
}
interface UseMarketDataReturn {
  data: Map<string, SymbolData>; isConnected: boolean; isAuthenticated: boolean;
  state: ConnectionState; error: string | null;
}

const symKey = (sym: string, exch: string) => `${exch}:${sym}`;
function normalizeMode(mode: SubscriptionMode): "LTP" | "QUOTE" | "DEPTH" {
  if (mode === "Quote") return "QUOTE";
  if (mode === "Depth") return "DEPTH";
  return "LTP";
}

/** Resilient live-data hook: reconnects, reauthenticates and replays demand. */
export function useMarketData({
  symbols, mode = "LTP", enabled = true,
}: UseMarketDataOptions): UseMarketDataReturn {
  const [data, setData] = useState<Map<string, SymbolData>>(new Map());
  const [state, setState] = useState<ConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribedRef = useRef<Set<string>>(new Set());
  const desiredRef = useRef(symbols);
  const modeRef = useRef(normalizeMode(mode));
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);

  const symbolsKey = useMemo(
    () => symbols.map((s) => symKey(s.symbol, s.exchange)).sort().join(","),
    [symbols],
  );
  const wireMode = normalizeMode(mode);

  useEffect(() => {
    desiredRef.current = symbols;
    modeRef.current = wireMode;
  }, [symbolsKey, wireMode, symbols]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let disposed = false;
    const subscriptions = subscribedRef.current;

    const clearReconnect = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const scheduleReconnect = (connect: () => void) => {
      if (disposed || reconnectTimerRef.current !== null) return;
      const attempt = reconnectAttemptRef.current++;
      const delay = Math.min(30_000, 750 * 2 ** Math.min(attempt, 6));
      setState("closed");
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    };

    const connect = async () => {
      if (disposed) return;
      clearReconnect();
      setState("connecting");
      try {
        const [cfg, apiKey] = await Promise.all([getWebSocketConfig(), getWebSocketApiKey()]);
        if (disposed) return;
        const ws = new WebSocket(cfg.websocket_url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (disposed || ws !== wsRef.current) return;
          setState("authenticating");
          ws.send(JSON.stringify({ action: "authenticate", api_key: apiKey }));
        };
        ws.onmessage = (evt) => {
          if (disposed || ws !== wsRef.current) return;
          let msg: Record<string, unknown>;
          try { msg = JSON.parse(evt.data as string); } catch { return; }
          if (msg.type === "auth") {
            if (msg.status === "success") {
              reconnectAttemptRef.current = 0;
              setError(null);
              setState("authenticated");
              subscriptions.clear();
              const desired = desiredRef.current;
              if (desired.length) {
                ws.send(JSON.stringify({ action: "subscribe", symbols: desired, mode: modeRef.current }));
                desired.forEach((s) => subscriptions.add(symKey(s.symbol, s.exchange)));
              }
            } else {
              const message = String(msg.message ?? "Authentication failed");
              setError(message);
              setState("error");
              notifyBrokerIssue({
                code: "BROKER_AUTH_REQUIRED", broker: String(msg.broker ?? "dhan"),
                message: `${message}. Re-login in Broker Configuration.`, action_url: "/broker/config",
              });
              ws.close();
            }
            return;
          }
          if (msg.type === "broker_issue") {
            notifyBrokerIssue(msg);
            setError(String(msg.message ?? "Broker data issue"));
            return;
          }
          if (msg.type !== "market_data") return;
          const symbol = String(msg.symbol ?? "");
          const exchange = String(msg.exchange ?? "");
          if (!symbol || !exchange) return;
          const tick = (msg.data as MarketTickData) ?? {};
          const key = symKey(symbol, exchange);
          setData((prev) => {
            const next = new Map(prev);
            next.set(key, {
              symbol, exchange,
              data: { ...(next.get(key)?.data ?? {}), ...tick },
              lastUpdate: Date.now(),
            });
            return next;
          });
        };
        ws.onerror = () => {
          if (disposed || ws !== wsRef.current) return;
          setError("Live data connection interrupted; reconnecting automatically");
          setState("error");
          try { ws.close(); } catch { /* close handler retries */ }
        };
        ws.onclose = () => {
          if (disposed || ws !== wsRef.current) return;
          wsRef.current = null;
          subscriptions.clear();
          scheduleReconnect(connect);
        };
      } catch (cause) {
        if (disposed) return;
        setError(cause instanceof Error ? cause.message : "Failed to start live data");
        setState("error");
        scheduleReconnect(connect);
      }
    };

    connect();
    return () => {
      disposed = true;
      clearReconnect();
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) try { ws.close(); } catch { /* ignore */ }
      subscriptions.clear();
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled || state !== "authenticated") return;
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const desired = new Set(symbols.map((s) => symKey(s.symbol, s.exchange)));
    const current = subscribedRef.current;
    const toAdd = symbols.filter((s) => !current.has(symKey(s.symbol, s.exchange)));
    const toRemove = [...current].filter((key) => !desired.has(key)).map((key) => {
      const split = key.indexOf(":");
      return { exchange: key.slice(0, split), symbol: key.slice(split + 1) };
    });
    if (toAdd.length) {
      ws.send(JSON.stringify({ action: "subscribe", symbols: toAdd, mode: wireMode }));
      toAdd.forEach((s) => current.add(symKey(s.symbol, s.exchange)));
    }
    if (toRemove.length) {
      ws.send(JSON.stringify({ action: "unsubscribe", symbols: toRemove, mode: wireMode }));
      toRemove.forEach((s) => current.delete(symKey(s.symbol, s.exchange)));
      setData((prev) => {
        const next = new Map(prev);
        toRemove.forEach((s) => next.delete(symKey(s.symbol, s.exchange)));
        return next;
      });
    }
  }, [symbolsKey, wireMode, enabled, state, symbols]);

  const effectiveState: ConnectionState = enabled ? state : "idle";
  return {
    data, state: effectiveState,
    isConnected: effectiveState === "connected" || effectiveState === "authenticated" || effectiveState === "authenticating",
    isAuthenticated: effectiveState === "authenticated", error,
  };
}
