/**
 * Futures-Risk Options client (matches /web/fr/* router).
 * Session-cookie authed via the shared axios instance.
 */

import api from "@/config/api";
import type {
  FrConfigMap,
  FrExpiry,
  FrFutures,
  FrStrikes,
  FrPhase,
  FrSymbolMap,
  FrTemplateTarget,
  FrTrade,
  ModifyTradePayload,
  PlaceTradePayload,
} from "@/types/futuresRisk";

interface Wrapped<T> {
  status: string;
  data: T;
}

// ---- Config ----
export async function getFrConfig(): Promise<FrConfigMap> {
  const r = await api.get<Wrapped<FrConfigMap>>("/web/fr/config");
  return r.data.data;
}
export async function setFrConfig(key: string, value: string): Promise<void> {
  await api.post("/web/fr/config", { key, value });
}

// ---- Target template ----
export async function listTargets(): Promise<FrTemplateTarget[]> {
  const r = await api.get<Wrapped<FrTemplateTarget[]>>("/web/fr/targets");
  return r.data.data;
}
export async function createTarget(points: number, exit_pct: number, enabled = true): Promise<FrTemplateTarget> {
  const r = await api.post<Wrapped<FrTemplateTarget>>("/web/fr/targets", { points, exit_pct, enabled });
  return r.data.data;
}
export async function updateTarget(
  id: number,
  fields: Partial<Pick<FrTemplateTarget, "points" | "exit_pct" | "enabled">>,
): Promise<FrTemplateTarget> {
  const r = await api.put<Wrapped<FrTemplateTarget>>(`/web/fr/targets/${id}`, fields);
  return r.data.data;
}
export async function deleteTarget(id: number): Promise<void> {
  await api.delete(`/web/fr/targets/${id}`);
}

// ---- Symbol map ----
export async function listSymbolMaps(): Promise<FrSymbolMap[]> {
  const r = await api.get<Wrapped<FrSymbolMap[]>>("/web/fr/symbol-maps");
  return r.data.data;
}
export async function createSymbolMap(data: Partial<FrSymbolMap>): Promise<FrSymbolMap> {
  const r = await api.post<Wrapped<FrSymbolMap>>("/web/fr/symbol-maps", data);
  return r.data.data;
}
export async function updateSymbolMap(id: number, data: Partial<FrSymbolMap>): Promise<FrSymbolMap> {
  const r = await api.put<Wrapped<FrSymbolMap>>(`/web/fr/symbol-maps/${id}`, data);
  return r.data.data;
}
export async function deleteSymbolMap(id: number): Promise<void> {
  await api.delete(`/web/fr/symbol-maps/${id}`);
}

// ---- Resolution helpers ----
export async function resolveFutures(underlying: string): Promise<FrFutures> {
  const r = await api.get<Wrapped<FrFutures>>("/web/fr/resolve-futures", { params: { underlying } });
  return r.data.data;
}
export async function listExpiries(underlying: string, exchange = "NSE_INDEX"): Promise<FrExpiry[]> {
  const r = await api.get<Wrapped<FrExpiry[]>>("/web/fr/expiries", { params: { underlying, exchange } });
  return r.data.data;
}
export async function listStrikes(
  underlying: string,
  expiry: string,
  option_type: string,
  exchange = "NSE_INDEX",
): Promise<FrStrikes> {
  const r = await api.get<Wrapped<FrStrikes>>("/web/fr/strikes", {
    params: { underlying, expiry, option_type, exchange },
  });
  return r.data.data;
}

// ---- Trades ----
export async function placeTrade(payload: PlaceTradePayload): Promise<FrTrade> {
  const r = await api.post<Wrapped<FrTrade>>("/web/fr/trade", payload);
  return r.data.data;
}
export async function listTrades(status = "all"): Promise<FrTrade[]> {
  const r = await api.get<Wrapped<FrTrade[]>>("/web/fr/trades", { params: { status } });
  return r.data.data;
}
export async function getTrade(id: number): Promise<FrTrade> {
  const r = await api.get<Wrapped<FrTrade>>(`/web/fr/trades/${id}`);
  return r.data.data;
}
export async function exitTrade(id: number): Promise<FrTrade> {
  const r = await api.post<Wrapped<FrTrade>>(`/web/fr/trades/${id}/exit`);
  return r.data.data;
}

// ---- Draft positions ----
export async function createDraft(payload: PlaceTradePayload): Promise<FrTrade> {
  const r = await api.post<Wrapped<FrTrade>>("/web/fr/trade/draft", payload);
  return r.data.data;
}
export async function placeDraft(id: number): Promise<FrTrade> {
  const r = await api.post<Wrapped<FrTrade>>(`/web/fr/trades/${id}/place`);
  return r.data.data;
}

// ---- Modify (draft or active) ----
export async function modifyTrade(id: number, fields: ModifyTradePayload): Promise<FrTrade> {
  const r = await api.put<Wrapped<FrTrade>>(`/web/fr/trades/${id}`, fields);
  return r.data.data;
}

// ---- Exits ----
export async function partialExit(id: number, qty: number): Promise<FrTrade> {
  const r = await api.post<Wrapped<FrTrade>>(`/web/fr/trades/${id}/partial-exit`, { qty });
  return r.data.data;
}
export async function emergencyExit(id: number): Promise<FrTrade> {
  const r = await api.post<Wrapped<FrTrade>>(`/web/fr/trades/${id}/emergency-exit`);
  return r.data.data;
}
export async function deleteTrade(id: number): Promise<void> {
  await api.delete(`/web/fr/trades/${id}`);
}

// ---- Phase history ----
export async function listPhases(underlying?: string): Promise<FrPhase[]> {
  const r = await api.get<Wrapped<FrPhase[]>>("/web/fr/phases", {
    params: underlying ? { underlying } : {},
  });
  return r.data.data;
}
